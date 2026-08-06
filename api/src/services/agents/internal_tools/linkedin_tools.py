"""
LinkedIn Tools for professional social media integration.
Uses LinkedIn API with OAuth 2.0 for user authentication.

Configuration stored in OAuthApp:
- provider: "linkedin"
- access_token from OAuth flow or API token

Capabilities:
- Get user profile
- Post text updates
- Post articles
- Share content with URLs
"""

import logging
from typing import Any

import httpx
from sqlalchemy import select

logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"


async def _get_linkedin_credentials(
    runtime_context: Any, tool_name: str = "internal_linkedin_get_profile"
) -> dict[str, Any]:
    """
    Get LinkedIn API credentials from OAuthApp via runtime context.

    This resolves the token by checking:
    1. User's personal token (user-first resolution)
    2. OAuth app token (fallback)

    Args:
        runtime_context: RuntimeContext with db_session
        tool_name: Name of the tool requesting access

    Returns:
        Dict with access_token

    Raises:
        ValueError: If no token is available
    """
    from src.models.agent_tool import AgentTool
    from src.models.oauth_app import OAuthApp
    from src.models.user_oauth_token import UserOAuthToken
    from src.services.agents.security import decrypt_value

    db = runtime_context.db_session

    # Get agent tool configuration
    result = await db.execute(
        select(AgentTool).filter(
            AgentTool.agent_id == runtime_context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
        )
    )
    agent_tool = result.scalar_one_or_none()

    if not agent_tool or not agent_tool.oauth_app_id:
        raise ValueError(f"No OAuth app configured for tool {tool_name}")

    # Get OAuth app (case-insensitive provider check)
    result = await db.execute(
        select(OAuthApp).filter(
            OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider.ilike("linkedin"), OAuthApp.is_active
        )
    )
    oauth_app = result.scalar_one_or_none()

    if not oauth_app:
        raise ValueError("No active LinkedIn OAuth app found")

    credentials = {}

    # Try user token first (user-first resolution)
    result = await db.execute(select(UserOAuthToken).filter(UserOAuthToken.oauth_app_id == oauth_app.id))
    user_token = result.scalar_one_or_none()

    if user_token and user_token.access_token:
        from datetime import UTC, datetime

        user_token_expired = user_token.token_expires_at is not None and user_token.token_expires_at.replace(
            tzinfo=UTC
        ) < datetime.now(UTC)
        if user_token_expired and user_token.refresh_token:
            try:
                from src.services.oauth.linkedin_oauth import LinkedInOAuth

                client_secret = decrypt_value(oauth_app.client_secret)
                li_oauth = LinkedInOAuth(
                    client_id=oauth_app.client_id,
                    client_secret=client_secret,
                    redirect_uri=oauth_app.redirect_uri,
                )
                refreshed = await li_oauth.refresh_access_token(decrypt_value(user_token.refresh_token))
                new_access = refreshed.get("access_token")
                new_refresh = refreshed.get("refresh_token")
                new_expires_in = refreshed.get("expires_in")
                if new_access:
                    from datetime import timedelta

                    from src.services.agents.security import encrypt_value as _enc

                    user_token.access_token = _enc(new_access)
                    if new_refresh:
                        user_token.refresh_token = _enc(new_refresh)
                    if new_expires_in:
                        user_token.token_expires_at = datetime.now(UTC) + timedelta(seconds=int(new_expires_in))
                    await db.commit()
                    logger.info(f"✅ Refreshed user LinkedIn token (OAuth app: '{oauth_app.app_name}')")
                    credentials["access_token"] = new_access
            except Exception as refresh_err:
                logger.warning(f"User LinkedIn token refresh failed: {refresh_err} — using stored token")
                credentials["access_token"] = decrypt_value(user_token.access_token)
        else:
            credentials["access_token"] = decrypt_value(user_token.access_token)
        logger.info(f"✅ Using user's LinkedIn token (OAuth app: '{oauth_app.app_name}')")
    elif oauth_app.access_token:
        # Fall back to OAuth app token, refreshing if expired
        from datetime import UTC, datetime

        token_expired = oauth_app.token_expires_at is not None and oauth_app.token_expires_at.replace(
            tzinfo=UTC
        ) < datetime.now(UTC)
        if token_expired and oauth_app.refresh_token:
            try:
                from src.services.oauth.linkedin_oauth import LinkedInOAuth

                client_secret = decrypt_value(oauth_app.client_secret)
                li_oauth = LinkedInOAuth(
                    client_id=oauth_app.client_id,
                    client_secret=client_secret,
                    redirect_uri=oauth_app.redirect_uri,
                )
                refreshed = await li_oauth.refresh_access_token(decrypt_value(oauth_app.refresh_token))
                new_access = refreshed.get("access_token")
                new_refresh = refreshed.get("refresh_token")
                new_expires_in = refreshed.get("expires_in")
                if new_access:
                    from datetime import timedelta

                    from src.services.agents.security import encrypt_value as _enc

                    oauth_app.access_token = _enc(new_access)
                    if new_refresh:
                        oauth_app.refresh_token = _enc(new_refresh)
                    if new_expires_in:
                        oauth_app.token_expires_at = datetime.now(UTC) + timedelta(seconds=int(new_expires_in))
                    await db.commit()
                    logger.info(f"✅ Refreshed LinkedIn token for app '{oauth_app.app_name}'")
                    credentials["access_token"] = new_access
            except Exception as refresh_err:
                logger.warning(f"LinkedIn token refresh failed: {refresh_err} — falling back to stored token")
                credentials["access_token"] = decrypt_value(oauth_app.access_token)
        else:
            credentials["access_token"] = decrypt_value(oauth_app.access_token)
        logger.info(f"✅ Using LinkedIn OAuth app token '{oauth_app.app_name}'")
    elif oauth_app.api_token:
        # Fall back to API token
        credentials["access_token"] = decrypt_value(oauth_app.api_token)
        logger.info(f"✅ Using LinkedIn API token '{oauth_app.app_name}'")

    if not credentials.get("access_token"):
        raise ValueError("No LinkedIn access token available. Please connect LinkedIn.")

    # Attach company page config so posting functions can switch author URN
    if agent_tool and agent_tool.config:
        credentials["post_to_company_page"] = bool(agent_tool.config.get("post_to_company_page"))
        credentials["company_page_id"] = agent_tool.config.get("company_page_id") or ""
    else:
        credentials["post_to_company_page"] = False
        credentials["company_page_id"] = ""

    return credentials


async def _make_linkedin_request(
    endpoint: str,
    method: str = "GET",
    credentials: dict[str, Any] = None,
    params: dict[str, Any] = None,
    json_data: dict[str, Any] = None,
    headers: dict[str, str] = None,
) -> dict[str, Any]:
    """Make authenticated request to LinkedIn API."""
    default_headers = {
        "Authorization": f"Bearer {credentials.get('access_token')}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202401",
    }

    if headers:
        default_headers.update(headers)

    url = f"{LINKEDIN_API_BASE}{endpoint}"

    async with httpx.AsyncClient() as client:
        if method == "GET":
            response = await client.get(url, headers=default_headers, params=params, timeout=30.0)
        elif method == "POST":
            response = await client.post(url, headers=default_headers, json=json_data, timeout=30.0)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        if response.status_code == 401:
            raise ValueError("LinkedIn authentication failed. Token may be expired.")
        elif response.status_code == 403:
            raise ValueError("LinkedIn API access forbidden. Check your app permissions.")
        elif response.status_code == 429:
            raise ValueError("LinkedIn API rate limit exceeded. Please try again later.")

        response.raise_for_status()

        # Handle empty responses (201 Created, 204 No Content)
        if response.status_code in (201, 204) or not response.content:
            # For 201 Created, extract ID from headers
            result = {"success": True}
            if "x-restli-id" in response.headers:
                result["id"] = response.headers["x-restli-id"]
            if "location" in response.headers:
                result["location"] = response.headers["location"]
            return result

        return response.json()


async def internal_linkedin_get_profile(
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Get the authenticated user's LinkedIn profile.

    Returns:
        User profile information
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_linkedin_get_profile")
        credentials = await _get_linkedin_credentials(runtime_context, tool_name)

        # Get basic profile using OpenID Connect userinfo endpoint
        result = await _make_linkedin_request(
            "/userinfo",
            credentials=credentials,
        )

        return {
            "success": True,
            "profile": {
                "id": result.get("sub"),
                "name": result.get("name"),
                "given_name": result.get("given_name"),
                "family_name": result.get("family_name"),
                "picture": result.get("picture"),
                "email": result.get("email"),
                "email_verified": result.get("email_verified"),
                "locale": result.get("locale"),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get LinkedIn profile: {e}")
        return {"success": False, "error": str(e)}


async def internal_linkedin_post_text(
    text: str,
    visibility: str = "PUBLIC",
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Post a text update to LinkedIn.

    Args:
        text: Post content (max 3000 characters)
        visibility: "PUBLIC", "CONNECTIONS", or "LOGGED_IN" (default: PUBLIC)

    Returns:
        Created post details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not text:
        return {"success": False, "error": "Post text is required"}

    if len(text) > 3000:
        return {"success": False, "error": f"Post exceeds 3000 characters ({len(text)} chars)"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_linkedin_get_profile")
        credentials = await _get_linkedin_credentials(runtime_context, tool_name)

        # First get the user's profile to get their URN
        profile_result = await internal_linkedin_get_profile(
            config=config,
            runtime_context=runtime_context,
        )

        if not profile_result.get("success"):
            return profile_result

        user_id = profile_result.get("profile", {}).get("id")
        if not user_id:
            return {"success": False, "error": "Failed to get user ID"}

        if credentials.get("post_to_company_page") and credentials.get("company_page_id"):
            author_urn = f"urn:li:organization:{credentials['company_page_id']}"
        else:
            author_urn = f"urn:li:person:{user_id}"

        # Create post using Posts API
        json_data = {
            "author": author_urn,
            "commentary": text,
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        result = await _make_linkedin_request(
            "/posts",
            method="POST",
            credentials=credentials,
            json_data=json_data,
        )

        # Extract post ID from response header or body
        post_id = result.get("id") or result.get("x-restli-id")

        return {
            "success": True,
            "post": {
                "id": post_id,
                "text": text,
                "visibility": visibility,
                "author": author_urn,
            },
            "message": "Post published successfully",
        }

    except Exception as e:
        logger.error(f"Failed to post to LinkedIn: {e}")
        return {"success": False, "error": str(e)}


async def internal_linkedin_share_url(
    url: str,
    text: str | None = None,
    title: str | None = None,
    description: str | None = None,
    visibility: str = "PUBLIC",
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Share a URL/article on LinkedIn.

    Args:
        url: URL to share
        text: Commentary text (optional)
        title: Title override for the shared content (optional)
        description: Description override (optional)
        visibility: "PUBLIC", "CONNECTIONS", or "LOGGED_IN" (default: PUBLIC)

    Returns:
        Created share details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not url:
        return {"success": False, "error": "URL is required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_linkedin_get_profile")
        credentials = await _get_linkedin_credentials(runtime_context, tool_name)

        # Get user profile for author URN
        profile_result = await internal_linkedin_get_profile(
            config=config,
            runtime_context=runtime_context,
        )

        if not profile_result.get("success"):
            return profile_result

        user_id = profile_result.get("profile", {}).get("id")
        if not user_id:
            return {"success": False, "error": "Failed to get user ID"}

        if credentials.get("post_to_company_page") and credentials.get("company_page_id"):
            author_urn = f"urn:li:organization:{credentials['company_page_id']}"
        else:
            author_urn = f"urn:li:person:{user_id}"

        # Create share with article content
        json_data = {
            "author": author_urn,
            "commentary": text or "",
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {
                "article": {
                    "source": url,
                    "title": title,
                    "description": description,
                }
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        # Remove None values from article
        json_data["content"]["article"] = {k: v for k, v in json_data["content"]["article"].items() if v is not None}

        result = await _make_linkedin_request(
            "/posts",
            method="POST",
            credentials=credentials,
            json_data=json_data,
        )

        post_id = result.get("id") or result.get("x-restli-id")

        return {
            "success": True,
            "share": {
                "id": post_id,
                "url": url,
                "text": text,
                "visibility": visibility,
            },
            "message": "URL shared successfully",
        }

    except Exception as e:
        logger.error(f"Failed to share on LinkedIn: {e}")
        return {"success": False, "error": str(e)}


async def internal_linkedin_get_company_info(
    company_id: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Get information about a LinkedIn company/organization.

    Args:
        company_id: LinkedIn company/organization ID

    Returns:
        Company information
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not company_id:
        return {"success": False, "error": "Company ID is required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_linkedin_get_profile")
        credentials = await _get_linkedin_credentials(runtime_context, tool_name)

        result = await _make_linkedin_request(
            f"/organizations/{company_id}",
            credentials=credentials,
        )

        return {
            "success": True,
            "company": {
                "id": result.get("id"),
                "name": result.get("localizedName"),
                "description": result.get("localizedDescription"),
                "website": result.get("websiteUrl"),
                "industry": result.get("localizedSpecialties"),
                "logo": result.get("logoV2", {}).get("original"),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get LinkedIn company info: {e}")
        return {"success": False, "error": str(e)}


async def internal_linkedin_get_posts(
    count: int = 10,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Get the authenticated user's LinkedIn posts/activity.

    NOTE: This feature requires LinkedIn Marketing API access with 'r_member_social' scope,
    which is a restricted permission requiring LinkedIn partner approval.
    Standard LinkedIn apps can post content but cannot read post history.

    Args:
        count: Number of posts to retrieve (max 100, default 10)

    Returns:
        List of user's recent posts
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    # Limit count to reasonable range
    count = min(max(1, count), 100)

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_linkedin_get_profile")
        credentials = await _get_linkedin_credentials(runtime_context, tool_name)

        # Get user profile for author URN
        profile_result = await internal_linkedin_get_profile(
            config=config,
            runtime_context=runtime_context,
        )

        if not profile_result.get("success"):
            return profile_result

        user_id = profile_result.get("profile", {}).get("id")
        if not user_id:
            return {"success": False, "error": "Failed to get user ID"}

        author_urn = f"urn:li:person:{user_id}"

        # Get posts using the Posts API with author filter
        # Note: This requires 'r_member_social' scope (Marketing API)
        result = await _make_linkedin_request(
            "/posts",
            credentials=credentials,
            params={
                "author": author_urn,
                "q": "author",
                "count": count,
            },
        )

        posts = []
        elements = result.get("elements", [])

        for post in elements:
            post_data = {
                "id": post.get("id"),
                "text": post.get("commentary"),
                "visibility": post.get("visibility"),
                "created_at": post.get("createdAt"),
                "last_modified": post.get("lastModifiedAt"),
                "lifecycle_state": post.get("lifecycleState"),
            }

            # Extract content info if present
            content = post.get("content", {})
            if content:
                if "article" in content:
                    post_data["article"] = {
                        "url": content["article"].get("source"),
                        "title": content["article"].get("title"),
                        "description": content["article"].get("description"),
                    }
                elif "media" in content:
                    post_data["media"] = content["media"]

            posts.append(post_data)

        return {
            "success": True,
            "posts": posts,
            "count": len(posts),
            "profile_id": user_id,
        }

    except ValueError as e:
        error_msg = str(e)
        # Provide more helpful error for permission issues
        if "forbidden" in error_msg.lower() or "403" in error_msg:
            logger.error(f"Failed to get LinkedIn posts: {e}")
            return {
                "success": False,
                "error": "Reading LinkedIn posts requires the 'r_member_social' scope, "
                "which is only available through LinkedIn's Marketing API partner program. "
                "Standard LinkedIn apps can post content but cannot read post history.",
            }
        return {"success": False, "error": error_msg}

    except Exception as e:
        logger.error(f"Failed to get LinkedIn posts: {e}")
        return {"success": False, "error": str(e)}


async def internal_linkedin_post_with_image(
    text: str,
    image_url: str | None = None,
    image_urls: list[str] | None = None,
    visibility: str = "PUBLIC",
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Post text with one or more images to LinkedIn using the proper Images API.

    Downloads each image, uploads it to LinkedIn, then creates the post.
    Uses `content.media` for a single image and `content.multiImage` for 2-9 images.

    Args:
        text: Post content
        image_url: URL of a single image (use image_urls for multiple)
        image_urls: List of image URLs (supports up to 9 images)
        visibility: "PUBLIC", "CONNECTIONS", or "LOGGED_IN"

    Returns:
        Created post details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not text:
        return {"success": False, "error": "Post text is required"}

    # Normalise: merge image_url + image_urls into one list
    all_urls: list[str] = []
    if image_urls:
        all_urls.extend(image_urls)
    if image_url and image_url not in all_urls:
        all_urls.append(image_url)

    if not all_urls:
        return {"success": False, "error": "At least one image URL is required"}

    if len(all_urls) > 9:
        return {"success": False, "error": "LinkedIn supports a maximum of 9 images per post"}

    try:
        import httpx

        config = config or {}
        tool_name = config.get("_tool_name", "internal_linkedin_get_profile")
        credentials = await _get_linkedin_credentials(runtime_context, tool_name)
        access_token = credentials.get("access_token")

        # Get user profile for author URN
        profile_result = await internal_linkedin_get_profile(
            config=config,
            runtime_context=runtime_context,
        )

        if not profile_result.get("success"):
            return profile_result

        user_id = profile_result.get("profile", {}).get("id")
        if not user_id:
            return {"success": False, "error": "Failed to get user ID"}

        if credentials.get("post_to_company_page") and credentials.get("company_page_id"):
            author_urn = f"urn:li:organization:{credentials['company_page_id']}"
        else:
            author_urn = f"urn:li:person:{user_id}"

        init_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # Upload all images and collect their URNs
        uploaded_urns: list[str] = []
        for idx, url in enumerate(all_urls):
            # Step 1: Download image bytes
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                img_response = await client.get(url)
                if img_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to download image {idx + 1} from URL (HTTP {img_response.status_code})",
                    }
                image_bytes = img_response.content
                content_type = img_response.headers.get("content-type", "image/jpeg").split(";")[0].strip()

            # Step 2: Initialize LinkedIn image upload
            async with httpx.AsyncClient(timeout=30.0) as client:
                init_response = await client.post(
                    "https://api.linkedin.com/v2/images?action=initializeUpload",
                    headers=init_headers,
                    json={"initializeUploadRequest": {"owner": author_urn}},
                )
                if init_response.status_code not in (200, 201):
                    error_detail = init_response.text
                    logger.error(f"LinkedIn image init failed: {error_detail}")
                    return {"success": False, "error": f"Failed to initialize LinkedIn image upload: {error_detail}"}
                init_data = init_response.json()

            upload_url = init_data.get("value", {}).get("uploadUrl")
            image_urn = init_data.get("value", {}).get("image")

            if not upload_url or not image_urn:
                return {"success": False, "error": "LinkedIn did not return upload URL or image URN"}

            # Step 3: Upload image binary
            async with httpx.AsyncClient(timeout=60.0) as client:
                upload_response = await client.put(
                    upload_url,
                    content=image_bytes,
                    headers={"Content-Type": content_type},
                )
                if upload_response.status_code not in (200, 201, 204):
                    logger.error(f"LinkedIn image upload failed: {upload_response.status_code} {upload_response.text}")
                    return {
                        "success": False,
                        "error": f"Failed to upload image {idx + 1} to LinkedIn (HTTP {upload_response.status_code})",
                    }

            logger.info(f"✅ Uploaded image {idx + 1}/{len(all_urls)} to LinkedIn: {image_urn}")
            uploaded_urns.append(image_urn)

        # Step 4: Build content block — single image vs multi-image
        if len(uploaded_urns) == 1:
            content_block = {"media": {"id": uploaded_urns[0]}}
        else:
            content_block = {"multiImage": {"images": [{"id": urn, "altText": ""} for urn in uploaded_urns]}}

        post_data = {
            "author": author_urn,
            "commentary": text,
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": content_block,
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        result = await _make_linkedin_request(
            "/posts",
            method="POST",
            credentials=credentials,
            json_data=post_data,
        )

        post_id = result.get("id") or result.get("x-restli-id")

        return {
            "success": True,
            "post": {
                "id": post_id,
                "text": text,
                "image_urns": uploaded_urns,
                "image_count": len(uploaded_urns),
                "visibility": visibility,
            },
            "message": f"Post with {len(uploaded_urns)} image(s) published successfully",
        }

    except Exception as e:
        logger.error(f"Failed to post image to LinkedIn: {e}")
        return {"success": False, "error": str(e)}


async def internal_linkedin_get_managed_pages(
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Get the LinkedIn Pages/Organizations that the authenticated user administers.
    Requires w_organization_social scope.

    Returns:
        List of managed pages with id and name
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_linkedin_get_profile")
        credentials = await _get_linkedin_credentials(runtime_context, tool_name)

        profile_result = await internal_linkedin_get_profile(config=config, runtime_context=runtime_context)
        if not profile_result.get("success"):
            return profile_result

        user_id = profile_result.get("profile", {}).get("id")
        if not user_id:
            return {"success": False, "error": "Failed to get user ID"}

        result = await _make_linkedin_request(
            "/organizationAcls",
            credentials=credentials,
            params={
                "q": "roleAssignee",
                "role": "ADMINISTRATOR",
                "projection": "(elements*(organization~(id,localizedName)))",
            },
        )

        pages = []
        for element in result.get("elements", []):
            org = element.get("organization~", {})
            if org:
                pages.append(
                    {
                        "id": str(org.get("id", "")),
                        "name": org.get("localizedName", ""),
                        "urn": f"urn:li:organization:{org.get('id', '')}",
                    }
                )

        return {"success": True, "pages": pages, "count": len(pages)}

    except Exception as e:
        logger.error(f"Failed to get LinkedIn managed pages: {e}")
        return {"success": False, "error": str(e)}


async def internal_linkedin_post_to_page(
    organization_id: str,
    text: str,
    visibility: str = "PUBLIC",
    url: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Post to a LinkedIn Page/Organization on behalf of the authenticated user.
    Requires w_organization_social scope.

    Args:
        organization_id: LinkedIn organization/page ID (numeric, e.g. '12345678')
        text: Post content (max 3000 characters)
        visibility: "PUBLIC" or "LOGGED_IN" (default: PUBLIC)
        url: Optional URL to share as article content

    Returns:
        Created post details
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not organization_id:
        return {"success": False, "error": "Organization ID is required"}

    if not text:
        return {"success": False, "error": "Post text is required"}

    if len(text) > 3000:
        return {"success": False, "error": f"Post exceeds 3000 characters ({len(text)} chars)"}

    try:
        config = config or {}
        tool_name = config.get("_tool_name", "internal_linkedin_get_profile")
        credentials = await _get_linkedin_credentials(runtime_context, tool_name)

        author_urn = f"urn:li:organization:{organization_id}"

        json_data: dict[str, Any] = {
            "author": author_urn,
            "commentary": text,
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        if url:
            json_data["content"] = {"article": {"source": url}}

        result = await _make_linkedin_request(
            "/posts",
            method="POST",
            credentials=credentials,
            json_data=json_data,
        )

        post_id = result.get("id") or result.get("x-restli-id")

        return {
            "success": True,
            "post": {
                "id": post_id,
                "text": text,
                "organization_id": organization_id,
                "author_urn": author_urn,
                "visibility": visibility,
            },
            "message": f"Post published to LinkedIn Page ({organization_id}) successfully",
        }

    except Exception as e:
        logger.error(f"Failed to post to LinkedIn page: {e}")
        return {"success": False, "error": str(e)}
