"""
GitHub Data Source Connector.

Handles syncing data from GitHub repositories, issues, pull requests, and discussions.
"""

import logging
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.data_source import DataSource
from src.services.agents.security import decrypt_value, normalize_pem_private_key

from .base_connector import BaseConnector

logger = logging.getLogger(__name__)


class GitHubConnector(BaseConnector):
    """Connector for GitHub data sources."""

    def __init__(self, data_source: DataSource, db: AsyncSession):
        """
        Initialize GitHub connector.

        Args:
            data_source: DataSource model instance
            db: Database session
        """
        super().__init__(data_source, db)
        self.base_url = "https://api.github.com"
        self._cached_installation_token: str | None = None

    async def _get_access_token(self) -> str:
        """Get decrypted access token from data source or linked OAuth app."""
        if self.data_source.access_token_encrypted:
            return decrypt_value(self.data_source.access_token_encrypted)

        if self.data_source.oauth_app_id and self.data_source.oauth_app:
            oauth_app = self.data_source.oauth_app

            if oauth_app.auth_method == "github_app":
                if not self._cached_installation_token:
                    self._cached_installation_token = await self._get_github_app_token(oauth_app)
                return self._cached_installation_token
            elif oauth_app.auth_method == "api_token":
                if not oauth_app.api_token:
                    raise ValueError(
                        "No API token configured. Please add a GitHub Personal Access Token to this OAuth app."
                    )
                return decrypt_value(oauth_app.api_token)
            else:
                if not oauth_app.access_token:
                    raise ValueError(
                        "No OAuth access token available. Please complete OAuth flow first or use API token method."
                    )
                return decrypt_value(oauth_app.access_token)

        raise ValueError("No access token configured for GitHub data source")

    async def _generate_app_jwt(self, oauth_app) -> str:
        """Generate a short-lived JWT to authenticate as the GitHub App itself."""
        import time

        import jwt

        app_id = oauth_app.client_id
        if not app_id:
            raise ValueError("GitHub App ID not configured (store in Client ID field).")
        if not oauth_app.client_secret:
            raise ValueError("GitHub App private key not configured (store in Client Secret field).")

        private_key_pem = normalize_pem_private_key(decrypt_value(oauth_app.client_secret))
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 600, "iss": str(app_id)}
        return jwt.encode(payload, private_key_pem, algorithm="RS256")

    async def _get_github_app_token(self, oauth_app) -> str:
        """Get installation access token by looking up installation ID from the first configured repo."""
        app_jwt = await self._generate_app_jwt(oauth_app)

        config = self.data_source.config or {}
        repositories = config.get("repositories", [])
        if not repositories:
            raise ValueError(
                "No repositories configured. Add at least one repository to use GitHub App authentication."
            )

        first_repo = repositories[0]
        if isinstance(first_repo, str):
            if "/" not in first_repo:
                raise ValueError(f"Invalid repository format: {first_repo}. Expected 'owner/repo'")
            owner, repo = first_repo.split("/", 1)
        elif isinstance(first_repo, dict):
            owner = first_repo.get("owner", "")
            repo = first_repo.get("name", "")
        else:
            raise ValueError(f"Invalid repository config: {first_repo}")

        if not owner or not repo:
            raise ValueError("Invalid repository configuration — cannot look up GitHub App installation.")

        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient() as client:
            inst_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/installation",
                headers=headers,
                timeout=15.0,
            )
            if inst_resp.status_code == 404:
                raise ValueError(
                    f"GitHub App is not installed on {owner}/{repo}. "
                    "Please install the GitHub App on the organization or repository first."
                )
            if inst_resp.status_code != 200:
                raise ValueError(f"Failed to look up GitHub App installation for {owner}/{repo}: {inst_resp.text}")

            installation_id = inst_resp.json()["id"]

            token_resp = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers=headers,
                timeout=15.0,
            )
            if token_resp.status_code != 201:
                raise ValueError(f"Failed to get GitHub App installation token: {token_resp.text}")

            logger.info("Got GitHub App installation token for %s/%s (installation %s)", owner, repo, installation_id)
            return token_resp.json()["token"]

    async def _make_request(
        self, method: str, endpoint: str, params: dict[str, Any] | None = None, json_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Make authenticated request to GitHub API.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            json_data: JSON body data

        Returns:
            Response data
        """
        token = await self._get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method, url=url, headers=headers, params=params, json=json_data, timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def connect(self) -> bool:
        """Establish connection to GitHub (test API access)."""
        try:
            oauth_app = self.data_source.oauth_app if self.data_source.oauth_app_id else None
            if oauth_app and oauth_app.auth_method == "github_app":
                app_jwt = await self._generate_app_jwt(oauth_app)
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://api.github.com/app",
                        headers={
                            "Authorization": f"Bearer {app_jwt}",
                            "Accept": "application/vnd.github+json",
                            "X-GitHub-Api-Version": "2022-11-28",
                        },
                        timeout=15.0,
                    )
                    resp.raise_for_status()
            else:
                await self._make_request("GET", "/user")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to GitHub: {e}")
            return False

    async def disconnect(self) -> None:
        """Close connection to GitHub."""
        # No persistent connection to close
        pass

    async def fetch_documents(self, since: datetime | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        """
        Fetch documents from GitHub.

        Args:
            since: Fetch documents modified since this timestamp
            limit: Maximum number of documents to fetch

        Returns:
            List of documents
        """
        documents = []
        config = self.data_source.config or {}
        repositories = config.get("repositories", [])

        # Handle case where repositories is a single string instead of a list
        if isinstance(repositories, str):
            repositories = [repositories]

        sync_issues = config.get("sync_issues", True)
        sync_pull_requests = config.get("sync_pull_requests", True)
        sync_discussions = config.get("sync_discussions", False)
        sync_code = config.get("sync_code", False)

        for repo in repositories:
            # Handle both string format "owner/repo" and object format {"owner": "x", "name": "y"}
            if isinstance(repo, str):
                # Parse "owner/repo" format
                if "/" in repo:
                    owner, name = repo.split("/", 1)
                else:
                    logger.warning(f"Invalid repository format: {repo}. Expected 'owner/repo'")
                    continue
            elif isinstance(repo, dict):
                owner = repo.get("owner")
                name = repo.get("name")
            else:
                logger.warning(f"Invalid repository config: {repo}")
                continue

            if not owner or not name:
                logger.warning(f"Invalid repository config: {repo}")
                continue

            logger.info(f"Syncing repository: {owner}/{name}")

            # Fetch README
            readme_docs = await self._sync_readme(owner, name)
            documents.extend(readme_docs)

            # Fetch issues if enabled
            if sync_issues:
                issue_docs = await self._sync_issues(owner, name)
                documents.extend(issue_docs)

            # Fetch PRs if enabled
            if sync_pull_requests:
                pr_docs = await self._sync_pull_requests(owner, name)
                documents.extend(pr_docs)

            # Fetch discussions if enabled
            if sync_discussions:
                discussion_docs = await self._sync_discussions(owner, name)
                documents.extend(discussion_docs)

            # Fetch code files if enabled
            if sync_code and isinstance(repo, dict):
                code_docs = await self._sync_code_files(owner, name, repo.get("paths", []))
                documents.extend(code_docs)

            if limit and len(documents) >= limit:
                break

        return documents[:limit] if limit else documents

    async def get_document_count(self) -> int:
        """Get total number of documents."""
        # Approximate count based on repositories
        config = self.data_source.config or {}
        repositories = config.get("repositories", [])
        # Rough estimate: README + 100 issues + 50 PRs per repo
        return len(repositories) * 151

    def get_required_config_fields(self) -> list[str]:
        """Get required configuration fields."""
        return ["repositories"]

    async def _create_document(self, title: str, content: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """
        Create a document dict for processing.

        Args:
            title: Document title
            content: Document content
            metadata: Document metadata

        Returns:
            Document dictionary
        """
        return {
            "id": f"{metadata.get('repository', 'unknown')}_{metadata.get('type', 'doc')}_{hash(title)}",
            "text": content,
            "metadata": {"title": title, "source": "github", **metadata},
        }

    async def _sync_readme(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """Sync repository README."""
        try:
            data = await self._make_request("GET", f"/repos/{owner}/{repo}/readme")

            # Decode base64 content
            import base64

            content = base64.b64decode(data["content"]).decode("utf-8")

            # Create document
            doc = await self._create_document(
                title=f"{owner}/{repo} - README",
                content=content,
                metadata={
                    "type": "readme",
                    "repository": f"{owner}/{repo}",
                    "path": data["path"],
                    "url": data["html_url"],
                },
            )

            return [doc]

        except Exception as e:
            logger.warning(f"Failed to sync README for {owner}/{repo}: {e}")
            return []

    async def _sync_issues(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """Sync repository issues."""
        documents = []

        try:
            # Get issues (includes pull requests by default, we'll filter them)
            issues = await self._make_request(
                "GET", f"/repos/{owner}/{repo}/issues", params={"state": "all", "per_page": 100}
            )

            for issue in issues:
                # Skip pull requests
                if "pull_request" in issue:
                    continue

                # Build content
                content = f"# {issue['title']}\n\n"
                content += f"**State:** {issue['state']}\n"
                content += f"**Created:** {issue['created_at']}\n"
                content += f"**Author:** {issue['user']['login']}\n\n"

                if issue.get("body"):
                    content += f"{issue['body']}\n\n"

                # Add comments
                if issue.get("comments", 0) > 0:
                    comments = await self._make_request(
                        "GET", f"/repos/{owner}/{repo}/issues/{issue['number']}/comments"
                    )

                    content += "## Comments\n\n"
                    for comment in comments:
                        content += f"**{comment['user']['login']}** ({comment['created_at']}):\n"
                        content += f"{comment['body']}\n\n"

                # Create document
                doc = await self._create_document(
                    title=f"Issue #{issue['number']}: {issue['title']}",
                    content=content,
                    metadata={
                        "type": "issue",
                        "repository": f"{owner}/{repo}",
                        "issue_number": issue["number"],
                        "state": issue["state"],
                        "url": issue["html_url"],
                        "labels": [label["name"] for label in issue.get("labels", [])],
                    },
                )

                if doc:
                    documents.append(doc)

            logger.info(f"Synced {len(documents)} issues from {owner}/{repo}")

        except Exception as e:
            logger.error(f"Failed to sync issues for {owner}/{repo}: {e}")

        return documents

    async def _sync_pull_requests(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """Sync repository pull requests."""
        documents = []

        try:
            prs = await self._make_request(
                "GET", f"/repos/{owner}/{repo}/pulls", params={"state": "all", "per_page": 100}
            )

            for pr in prs:
                # Build content
                content = f"# {pr['title']}\n\n"
                content += f"**State:** {pr['state']}\n"
                content += f"**Created:** {pr['created_at']}\n"
                content += f"**Author:** {pr['user']['login']}\n"
                content += f"**Base:** {pr['base']['ref']} <- **Head:** {pr['head']['ref']}\n\n"

                if pr.get("body"):
                    content += f"{pr['body']}\n\n"

                # Create document
                doc = await self._create_document(
                    title=f"PR #{pr['number']}: {pr['title']}",
                    content=content,
                    metadata={
                        "type": "pull_request",
                        "repository": f"{owner}/{repo}",
                        "pr_number": pr["number"],
                        "state": pr["state"],
                        "url": pr["html_url"],
                        "base_branch": pr["base"]["ref"],
                        "head_branch": pr["head"]["ref"],
                    },
                )

                if doc:
                    documents.append(doc)

            logger.info(f"Synced {len(documents)} pull requests from {owner}/{repo}")

        except Exception as e:
            logger.error(f"Failed to sync pull requests for {owner}/{repo}: {e}")

        return documents

    async def _sync_discussions(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """Sync repository discussions (requires GraphQL API)."""
        # Discussion sync requires GitHub GraphQL API - not yet implemented
        logger.info(f"Discussion sync not yet implemented for {owner}/{repo}")
        return []

    async def _sync_code_files(self, owner: str, repo: str, paths: list[str]) -> list[dict[str, Any]]:
        """Sync specific code files from repository."""
        documents = []

        try:
            for path in paths:
                try:
                    data = await self._make_request("GET", f"/repos/{owner}/{repo}/contents/{path}")

                    # Handle directory
                    if isinstance(data, list):
                        logger.info(f"Skipping directory: {path}")
                        continue

                    # Decode base64 content
                    import base64

                    content = base64.b64decode(data["content"]).decode("utf-8")

                    # Create document
                    doc = await self._create_document(
                        title=f"{owner}/{repo}/{path}",
                        content=content,
                        metadata={
                            "type": "code",
                            "repository": f"{owner}/{repo}",
                            "path": path,
                            "url": data["html_url"],
                            "size": data["size"],
                        },
                    )

                    if doc:
                        documents.append(doc)

                except Exception as e:
                    logger.warning(f"Failed to sync file {path}: {e}")

            logger.info(f"Synced {len(documents)} code files from {owner}/{repo}")

        except Exception as e:
            logger.error(f"Failed to sync code files for {owner}/{repo}: {e}")

        return documents

    async def test_connection(self) -> dict[str, Any]:
        """Test GitHub connection."""
        try:
            oauth_app = self.data_source.oauth_app if self.data_source.oauth_app_id else None
            if oauth_app and oauth_app.auth_method == "github_app":
                app_jwt = await self._generate_app_jwt(oauth_app)
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://api.github.com/app",
                        headers={
                            "Authorization": f"Bearer {app_jwt}",
                            "Accept": "application/vnd.github+json",
                            "X-GitHub-Api-Version": "2022-11-28",
                        },
                        timeout=15.0,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                return {
                    "success": True,
                    "message": f"Connected as GitHub App: {data.get('name', 'unknown')}",
                    "app": {"name": data.get("name"), "id": data.get("id"), "slug": data.get("slug")},
                }
            else:
                user = await self._make_request("GET", "/user")
                return {
                    "success": True,
                    "message": f"Connected as {user['login']}",
                    "user": {"login": user["login"], "name": user.get("name"), "email": user.get("email")},
                }
        except Exception as e:
            logger.error(f"GitHub connection test failed: {e}")
            return {"success": False, "error": str(e)}
