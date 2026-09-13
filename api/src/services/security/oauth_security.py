"""
OAuth security utilities.

Provides security functions for OAuth flows including redirect URL validation
and error message sanitization.
"""

import logging
import os
from urllib.parse import quote, urlparse

logger = logging.getLogger(__name__)


def validate_redirect_url(redirect_url: str, allowed_base_url: str) -> tuple[bool, str | None]:
    """
    Validate that a redirect URL is safe and within allowed domains.

    SECURITY: Prevents open redirect attacks by ensuring the redirect URL
    is within the application's domain.

    Args:
        redirect_url: The URL to validate
        allowed_base_url: The base URL that redirects should be within

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not redirect_url:
        return False, "Redirect URL is required"

    try:
        redirect_parsed = urlparse(redirect_url)
        allowed_parsed = urlparse(allowed_base_url)

        # Must have a scheme and netloc
        if not redirect_parsed.scheme or not redirect_parsed.netloc:
            return False, "Invalid redirect URL format"

        # Only allow http/https
        if redirect_parsed.scheme not in ("http", "https"):
            return False, "Redirect URL must use HTTP or HTTPS"

        # Check if the redirect URL is within the allowed domain
        # Allow exact match or subdomain match
        redirect_host = redirect_parsed.netloc.lower()
        allowed_host = allowed_parsed.netloc.lower()

        # Remove port for comparison if present
        redirect_domain = redirect_host.split(":")[0]
        allowed_domain = allowed_host.split(":")[0]

        # Check exact match
        if redirect_domain == allowed_domain:
            return True, None

        # Check subdomain match (e.g., app.example.com is allowed for example.com)
        # SECURITY: Only allow one level of subdomain to prevent subdomain takeover
        if redirect_domain.endswith(f".{allowed_domain}"):
            subdomain_part = redirect_domain[: -len(f".{allowed_domain}")]
            if "." not in subdomain_part:  # single-level subdomain only
                return True, None

        # Always allow localhost redirects — they are not an open-redirect risk to
        # external attackers and are necessary for local-frontend / tunnel-API setups.
        localhost_variants = {"localhost", "127.0.0.1", "0.0.0.0"}
        if redirect_domain in localhost_variants:
            return True, None

        # Also accept the operator-configured APP_BASE_URL (may differ from DB value)
        env_base_url = os.getenv("APP_BASE_URL", "").rstrip("/")
        if env_base_url:
            env_parsed = urlparse(env_base_url)
            env_domain = env_parsed.netloc.lower().split(":")[0]
            if redirect_domain == env_domain:
                return True, None
            if redirect_domain.endswith(f".{env_domain}"):
                env_subdomain_part = redirect_domain[: -len(f".{env_domain}")]
                if "." not in env_subdomain_part:  # single-level subdomain only
                    return True, None

        return False, f"Redirect URL domain '{redirect_domain}' is not allowed"

    except Exception as e:
        logger.warning(f"Error validating redirect URL: {e}")
        return False, "Invalid redirect URL"


def sanitize_redirect_url(redirect_url: str | None, default_url: str, base_url: str) -> str:
    """
    Sanitize and validate a redirect URL, returning a safe default if invalid.

    Args:
        redirect_url: The URL to sanitize
        default_url: Default URL to use if redirect_url is invalid
        base_url: The base URL that redirects should be within

    Returns:
        A safe redirect URL
    """
    if not redirect_url:
        return default_url

    is_valid, _ = validate_redirect_url(redirect_url, base_url)
    if is_valid:
        return redirect_url

    logger.warning(f"SECURITY: Rejected invalid redirect URL: {redirect_url}")
    return default_url


def url_encode_error_message(message: str) -> str:
    """
    URL-encode an error message for safe inclusion in redirect URLs.

    SECURITY: Prevents injection attacks by properly encoding special characters
    in error messages before including them in URLs.

    Args:
        message: The error message to encode

    Returns:
        URL-encoded message
    """
    if not message:
        return ""

    # Truncate very long messages to prevent URL length issues
    max_length = 200
    if len(message) > max_length:
        message = message[:max_length] + "..."

    # URL-encode the message
    return quote(str(message), safe="")


def build_oauth_redirect_url(
    base_redirect_url: str, success: bool, provider: str, error_message: str | None = None, **kwargs
) -> str:
    """
    Build a safe OAuth redirect URL with properly encoded parameters.

    Args:
        base_redirect_url: The base URL to redirect to
        success: Whether the OAuth flow was successful
        provider: The OAuth provider name
        error_message: Optional error message (will be URL-encoded)
        **kwargs: Additional parameters to include

    Returns:
        Complete redirect URL with encoded parameters
    """
    # Build query parameters
    params = []

    if success:
        params.append("oauth=success")
    else:
        params.append("oauth=error")

    params.append(f"provider={quote(provider, safe='')}")

    if error_message:
        encoded_message = url_encode_error_message(error_message)
        params.append(f"message={encoded_message}")

    # Add additional kwargs (URL-encoded)
    for key, value in kwargs.items():
        if value is not None:
            encoded_value = quote(str(value), safe="")
            params.append(f"{quote(key, safe='')}={encoded_value}")

    # Build final URL
    separator = "&" if "?" in base_redirect_url else "?"
    return f"{base_redirect_url}{separator}{'&'.join(params)}"
