"""
Blog Site Creation Tools - Agentic Approach

This module provides MINIMAL scaffolding tools for blog site creation.
The agent dynamically generates all CSS, HTML, and content based on user requirements.

NO hardcoded templates - the agent creates everything using:
- internal_generate_blog_site: Creates directory structure only
- internal_write_file: Agent writes custom CSS/HTML/JS
- internal_create_github_repository: Creates GitHub repo
- internal_deploy_blog_to_github: Deploys to GitHub
- internal_enable_github_pages: Enables GitHub Pages

The agent can create ANY style (Medium, Minimal, Modern, etc.) by generating
custom CSS and HTML dynamically based on user's description.
"""

import html
import logging
import os
import uuid
from datetime import datetime
from typing import Any

import httpx

from src.services.oauth.http_client import get_httpx_client

from .git_helpers import async_makedirs, async_path_exists, async_run_git_command, async_write_file

logger = logging.getLogger(__name__)


def _get_workspace_path(config: dict[str, Any] | None) -> str | None:
    """Get the workspace path from config or RuntimeContext (including Celery task fallback)."""
    from src.services.agents.workspace_manager import get_workspace_path_from_config

    return get_workspace_path_from_config(config)


def _validate_path_in_workspace(path: str, workspace_path: str | None) -> tuple[bool, str | None]:
    """Validate that a path is within the workspace directory."""
    if not workspace_path:
        return False, "No workspace path configured. File operations require a valid workspace."

    try:
        real_path = os.path.realpath(path)
        real_workspace = os.path.realpath(workspace_path)
        real_path = real_path.removeprefix("/private")
        real_workspace = real_workspace.removeprefix("/private")

        if not (real_path.startswith(real_workspace + os.sep) or real_path == real_workspace):
            return False, f"Path '{path}' is outside the workspace directory"

        return True, None
    except Exception as e:
        return False, f"Error validating path: {str(e)}"


async def internal_generate_blog_site(
    site_name: str,
    description: str = "",
    author_name: str = "Author",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate a minimal blog site structure (directories and placeholder files).

    This creates ONLY the basic scaffolding. The agent should then use
    internal_write_file to create custom CSS, HTML posts, and JavaScript
    based on the user's style requirements.

    IMPORTANT: The site is created within the workspace directory.

    The agent is responsible for:
    1. Generating CSS that matches user's desired style (Medium, Minimal, etc.)
    2. Creating the index.html with proper structure
    3. Writing blog posts as HTML files
    4. Adding any JavaScript functionality

    Args:
        site_name: Name of the blog site
        description: Description/tagline for the blog
        author_name: Name of the blog author
        config: Optional configuration dictionary

    Returns:
        Dictionary with:
        - site_path: Path to the generated site directory
        - structure: Directory structure created
        - instructions: Guide for the agent on next steps
    """
    try:
        logger.info(f"Creating blog site scaffolding for: {site_name}")

        # Get workspace path
        workspace_path = _get_workspace_path(config)
        if not workspace_path:
            return {"success": False, "error": "No workspace path configured. Cannot create blog site."}

        # Create site directory within workspace
        safe_name = "".join(c if c.isalnum() or c in "_ -" else "_" for c in site_name)[:50]
        site_dir_name = f"blog_{safe_name.replace(' ', '_')}_{uuid.uuid4().hex[:8]}"
        temp_dir = os.path.join(workspace_path, "sites", site_dir_name)
        await async_makedirs(temp_dir, config)

        # Create directory structure
        dirs = ["posts", "images", "css", "js"]
        for dir_name in dirs:
            await async_makedirs(os.path.join(temp_dir, dir_name), config)

        # Create minimal placeholder files (agent will overwrite with custom content)
        now = datetime.now()
        year = now.year

        # Minimal index.html - agent should replace with styled version
        safe_site_name = html.escape(site_name)
        safe_description = html.escape(description or site_name)
        index_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{safe_description}">
    <title>{safe_site_name}</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <header>
        <h1>{safe_site_name}</h1>
        <p>{html.escape(description or "Welcome to my blog")}</p>
    </header>
    <main>
        <section id="posts">
            <!-- Add blog post links here -->
        </section>
    </main>
    <footer>
        <p>&copy; {year} {safe_site_name}</p>
    </footer>
    <script src="js/app.js"></script>
</body>
</html>"""

        await async_write_file(os.path.join(temp_dir, "index.html"), index_content, config)
        await async_write_file(
            os.path.join(temp_dir, "css", "style.css"),
            "/* Agent will generate custom CSS based on user's style requirements */\n",
            config,
        )
        await async_write_file(
            os.path.join(temp_dir, "js", "app.js"),
            "// Blog site JavaScript\nconsole.log('Blog loaded');\n",
            config,
        )

        return {
            "success": True,
            "site_path": temp_dir,
            "site_name": site_name,
            "description": description,
            "author_name": author_name,
            "structure": {
                "root": temp_dir,
                "index.html": os.path.join(temp_dir, "index.html"),
                "css/style.css": os.path.join(temp_dir, "css", "style.css"),
                "js/app.js": os.path.join(temp_dir, "js", "app.js"),
                "posts/": os.path.join(temp_dir, "posts"),
                "images/": os.path.join(temp_dir, "images"),
            },
            "instructions": {
                "step_1": "Use internal_write_file to create css/style.css with custom CSS for the user's desired style",
                "step_2": "Use internal_write_file to update index.html with properly styled HTML structure",
                "step_3": "Use internal_write_file to create posts/*.html for each blog post",
                "step_4": "Use internal_write_file for about.html and other pages as needed",
                "step_5": "Use internal_create_github_repository to create a repo",
                "step_6": "Use internal_deploy_blog_to_github to push the site",
                "step_7": "Use internal_enable_github_pages to publish online",
            },
            "tips": {
                "medium_style": "Use Georgia/serif fonts, max-width 680px, clean typography, green accent (#1a8917)",
                "minimal_style": "System fonts, lots of whitespace, max-width 640px, simple black/white",
                "modern_style": "Inter font, gradients, rounded corners, card-based layout",
                "dark_style": "Dark background (#0d1117), light text, blue accent (#58a6ff)",
                "magazine_style": "Playfair Display headings, multi-column grid, featured posts",
            },
        }

    except Exception as e:
        logger.error(f"Error creating blog site scaffolding: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to create blog site: {str(e)}"}


async def internal_create_github_repo(
    repo_name: str,
    description: str = "",
    private: bool = False,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a new GitHub repository using the GitHub API.

    Requires GitHub token in config or environment variable GITHUB_TOKEN.

    Args:
        repo_name: Name for the new repository (will be part of URL)
        description: Repository description
        private: Whether repository should be private (default: False for GitHub Pages)
        config: Configuration with github_token

    Returns:
        Dictionary with repo details (url, clone_url, etc.) or error
    """
    try:
        # Get GitHub token from config or environment
        github_token = None
        if config:
            github_token = config.get("github_token")
        if not github_token:
            github_token = os.environ.get("GITHUB_TOKEN")

        if not github_token:
            return {
                "success": False,
                "error": "GitHub token not provided. Please connect your GitHub account or set GITHUB_TOKEN.",
            }

        # Create repository via GitHub API
        client = await get_httpx_client()
        response = await client.post(
            "https://api.github.com/user/repos",
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "name": repo_name,
                "description": description,
                "private": private,
                "auto_init": False,
            },
            timeout=30,
        )

        if response.status_code == 201:
            data = response.json()
            return {
                "success": True,
                "repo_name": data["name"],
                "repo_url": data["html_url"],
                "clone_url": data["clone_url"],
                "ssh_url": data["ssh_url"],
                "owner": data["owner"]["login"],
                "default_branch": data.get("default_branch", "main"),
            }
        elif response.status_code == 422:
            return {"success": False, "error": f"Repository '{repo_name}' may already exist or name is invalid."}
        else:
            return {"success": False, "error": f"GitHub API error ({response.status_code}): {response.text}"}

    except httpx.RequestError as e:
        logger.error(f"GitHub API request failed: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to connect to GitHub: {str(e)}"}
    except Exception as e:
        logger.error(f"Error creating GitHub repo: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to create repository: {str(e)}"}


async def internal_deploy_to_github(
    site_path: str,
    repo_url: str,
    branch: str = "main",
    commit_message: str = "Deploy blog site",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Deploy the blog site to GitHub by initializing git and pushing.

    Runs git commands to initialize the repository, add files, commit, and push.
    IMPORTANT: site_path must be within the workspace directory.

    Args:
        site_path: Path to the blog site directory (must be within workspace)
        repo_url: GitHub repository URL (HTTPS or SSH)
        branch: Branch name (default: main)
        commit_message: Commit message
        config: Optional configuration

    Returns:
        Dictionary with deployment status
    """
    try:
        # Validate site_path is within workspace
        workspace_path = _get_workspace_path(config)
        is_valid, error = _validate_path_in_workspace(site_path, workspace_path)
        if not is_valid:
            return {"success": False, "error": error}

        if not await async_path_exists(site_path, config):
            return {"success": False, "error": f"Site path not found: {site_path}"}

        # Git commands to execute
        commands = [
            ["git", "init"],
            ["git", "add", "."],
            ["git", "commit", "-m", commit_message],
            ["git", "branch", "-M", branch],
            ["git", "remote", "add", "origin", repo_url],
            ["git", "push", "-u", "origin", branch],
        ]

        results = []
        for cmd in commands:
            result = await async_run_git_command(cmd, site_path, config, timeout=120)
            results.append(
                {
                    "command": " ".join(cmd),
                    "returncode": result.get("return_code", -1),
                    "stdout": result.get("output", "")[:500],
                    "stderr": result.get("error", "")[:500],
                }
            )

            if not result["success"] and "remote origin already exists" not in result.get("error", ""):
                if "git push" in " ".join(cmd):
                    return {"success": False, "error": f"Git push failed: {result.get('error')}", "results": results}

        return {
            "success": True,
            "site_path": site_path,
            "repo_url": repo_url,
            "branch": branch,
            "message": "Site deployed to GitHub successfully!",
            "results": results,
        }

    except Exception as e:
        logger.error(f"Error deploying to GitHub: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to deploy: {str(e)}"}


async def internal_enable_github_pages(
    repo_name: str,
    owner: str,
    branch: str = "main",
    path: str = "/",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Enable GitHub Pages for a repository.

    Enables GitHub Pages hosting so the blog is publicly accessible.
    The site will be available at: https://{owner}.github.io/{repo_name}/

    Args:
        repo_name: Name of the repository
        owner: GitHub username (repository owner)
        branch: Branch to deploy (default: main)
        path: Path in repository (default: "/" for root)
        config: Configuration with github_token

    Returns:
        Dictionary with GitHub Pages URL and status
    """
    try:
        # Get GitHub token
        github_token = None
        if config:
            github_token = config.get("github_token")
        if not github_token:
            github_token = os.environ.get("GITHUB_TOKEN")

        if not github_token:
            return {"success": False, "error": "GitHub token required. Please connect your GitHub account."}

        # Enable GitHub Pages via API
        client = await get_httpx_client()
        response = await client.post(
            f"https://api.github.com/repos/{owner}/{repo_name}/pages",
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={"source": {"branch": branch, "path": path}},
            timeout=30,
        )

        pages_url = f"https://{owner}.github.io/{repo_name}/"

        if response.status_code in [201, 204]:
            return {
                "success": True,
                "pages_url": pages_url,
                "message": f"GitHub Pages enabled! Your site will be live at {pages_url}",
                "note": "It may take a few minutes for the site to be available.",
            }
        elif response.status_code == 409:
            return {"success": True, "pages_url": pages_url, "message": f"GitHub Pages already enabled at {pages_url}"}
        else:
            return {"success": False, "error": f"GitHub API error ({response.status_code}): {response.text}"}

    except httpx.RequestError as e:
        logger.error(f"GitHub Pages API request failed: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to connect to GitHub: {str(e)}"}
    except Exception as e:
        logger.error(f"Error enabling GitHub Pages: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to enable GitHub Pages: {str(e)}"}
