"""
Pull Request Review Tools for Code Intelligence.

Provides tools for analyzing and reviewing GitHub pull requests with security,
quality, and best practices checks.
"""

import base64
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def _get_github_token(
    runtime_context: dict[str, Any],
    config: dict[str, Any] | None = None,
    owner: str | None = None,
    repo: str | None = None,
) -> str:
    """Get GitHub token from runtime context or OAuth app."""
    from src.services.agents.internal_tools.github_auth_helper import get_github_token_from_context

    # Extract tool_name from config (added by adk_tools.py)
    tool_name = None
    if config:
        tool_name = config.get("_tool_name")

    if not tool_name:
        logger.warning("⚠️ No _tool_name in config, using fallback 'pr_review_tools'")
        tool_name = "pr_review_tools"

    logger.info(f"🔍 [PR Review Tools] Looking up GitHub OAuth for tool_name='{tool_name}' (owner={owner!r})")

    token = await get_github_token_from_context(runtime_context, tool_name=tool_name, owner=owner, repo=repo)

    if not token:
        raise ValueError("GitHub token not found. Please configure GitHub OAuth or provide a token.")

    return token


async def _make_github_request(
    method: str,
    endpoint: str,
    token: str,
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make authenticated request to GitHub API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    url = f"https://api.github.com{endpoint}"

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method, url=url, headers=headers, params=params, json=json_data, timeout=30.0
        )
        response.raise_for_status()
        return response.json()


async def internal_get_pr_details(
    owner: str,
    repo: str,
    pr_number: int,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get detailed information about a pull request.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with PR details
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        # Get PR details
        pr_data = await _make_github_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}", token)

        # Get PR files
        files_data = await _make_github_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/files", token)

        # Get PR commits
        commits_data = await _make_github_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/commits", token)

        # Get existing reviews
        reviews_data = await _make_github_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews", token)

        # Parse changed files
        changed_files = []
        total_additions = 0
        total_deletions = 0

        for file in files_data:
            changed_files.append(
                {
                    "filename": file["filename"],
                    "status": file["status"],
                    "additions": file["additions"],
                    "deletions": file["deletions"],
                    "changes": file["changes"],
                    "patch": file.get("patch", ""),
                    "blob_url": file.get("blob_url", ""),
                }
            )
            total_additions += file["additions"]
            total_deletions += file["deletions"]

        return {
            "success": True,
            "pr": {
                "number": pr_data["number"],
                "title": pr_data["title"],
                "body": pr_data.get("body", ""),
                "state": pr_data["state"],
                "draft": pr_data.get("draft", False),
                "author": pr_data["user"]["login"],
                "created_at": pr_data["created_at"],
                "updated_at": pr_data["updated_at"],
                "merged": pr_data.get("merged", False),
                "mergeable": pr_data.get("mergeable"),
                "base_branch": pr_data["base"]["ref"],
                "head_branch": pr_data["head"]["ref"],
                "html_url": pr_data["html_url"],
                "labels": [label["name"] for label in pr_data.get("labels", [])],
            },
            "files": changed_files,
            "stats": {
                "total_files": len(changed_files),
                "total_additions": total_additions,
                "total_deletions": total_deletions,
                "total_changes": total_additions + total_deletions,
                "total_commits": len(commits_data),
            },
            "commits": [
                {
                    "sha": commit["sha"],
                    "message": commit["commit"]["message"],
                    "author": commit["commit"]["author"]["name"],
                    "date": commit["commit"]["author"]["date"],
                }
                for commit in commits_data
            ],
            "existing_reviews": [
                {
                    "id": review["id"],
                    "user": review["user"]["login"],
                    "state": review["state"],
                    "submitted_at": review["submitted_at"],
                    "body": review.get("body", ""),
                }
                for review in reviews_data
            ],
        }

    except Exception as e:
        logger.error(f"Failed to get PR details: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_pr_diff(
    owner: str,
    repo: str,
    pr_number: int,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get the full diff of a pull request.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with PR diff
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3.diff",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            diff_content = response.text

        return {"success": True, "diff": diff_content, "size_bytes": len(diff_content.encode("utf-8"))}

    except Exception as e:
        logger.error(f"Failed to get PR diff: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_post_pr_review(
    owner: str,
    repo: str,
    pr_number: int,
    review_body: str,
    review_event: str = "COMMENT",
    review_comments: list[dict[str, Any]] | None = None,
    commit_id: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Post a review on a pull request.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        review_body: Review comment body
        review_event: Review event (COMMENT, APPROVE, REQUEST_CHANGES)
        review_comments: List of inline comments with path, line, and body.
            Each comment requires: path (str), line (int), body (str).
            Requires commit_id to be set.
        commit_id: The SHA of the head commit to attach the review to.
            Required when review_comments are provided. Get this from
            internal_github_get_pr_details commits[last].sha
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with review result
    """
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        # Validate review event
        valid_events = ["COMMENT", "APPROVE", "REQUEST_CHANGES"]
        if review_event not in valid_events:
            return {"success": False, "error": f"Invalid review_event. Must be one of: {valid_events}"}

        # Build review data
        review_data: dict[str, Any] = {"body": review_body, "event": review_event}

        if review_comments:
            if not commit_id:
                # Auto-fetch the head commit SHA so inline comments work
                try:
                    pr_data = await _make_github_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}", token)
                    commit_id = pr_data["head"]["sha"]
                    logger.info(f"Auto-fetched commit_id {commit_id} for PR #{pr_number} inline review")
                except Exception as fetch_err:
                    logger.warning(
                        f"Could not auto-fetch commit_id, posting review without inline comments: {fetch_err}"
                    )
                    review_comments = None

            if review_comments and commit_id:
                review_data["commit_id"] = commit_id
                review_data["comments"] = review_comments

        if commit_id and not review_comments:
            review_data["commit_id"] = commit_id

        # Post review
        result = await _make_github_request(
            "POST", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews", token, json_data=review_data
        )

        return {
            "success": True,
            "review_id": result["id"],
            "html_url": result["html_url"],
            "state": result["state"],
            "submitted_at": result["submitted_at"],
        }

    except Exception as e:
        logger.error(f"Failed to post PR review: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_analyze_pr_security(
    owner: str,
    repo: str,
    pr_number: int,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Analyze PR for security vulnerabilities and patterns.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with security analysis
    """
    try:
        # Get PR details
        pr_details = await internal_get_pr_details(owner, repo, pr_number, config, runtime_context)

        if not pr_details["success"]:
            return pr_details

        security_findings = []

        # Analyze each file for security patterns
        for file in pr_details["files"]:
            filename = file["filename"]
            patch = file.get("patch", "")

            # Check for common security issues
            findings = []

            # SQL Injection patterns
            if any(keyword in patch.lower() for keyword in ["execute", "query", "sql"]):
                if "+" in patch or "concat" in patch.lower():
                    findings.append(
                        {
                            "severity": "high",
                            "category": "sql_injection",
                            "message": "Potential SQL injection: String concatenation in SQL query",
                            "file": filename,
                        }
                    )

            # XSS patterns
            if any(keyword in patch.lower() for keyword in ["innerhtml", "dangerouslysetinnerhtml"]):
                findings.append(
                    {
                        "severity": "high",
                        "category": "xss",
                        "message": "Potential XSS: Direct HTML rendering without sanitization",
                        "file": filename,
                    }
                )

            # Hardcoded secrets
            secret_patterns = ["password", "api_key", "secret", "token", "credential"]
            for pattern in secret_patterns:
                if f"{pattern} =" in patch.lower() or f"{pattern}:" in patch.lower():
                    findings.append(
                        {
                            "severity": "critical",
                            "category": "secrets",
                            "message": f"Potential hardcoded secret: {pattern}",
                            "file": filename,
                        }
                    )

            # Command injection
            if any(keyword in patch for keyword in ["exec(", "eval(", "system(", "shell_exec"]):
                findings.append(
                    {
                        "severity": "critical",
                        "category": "command_injection",
                        "message": "Potential command injection: Unsafe code execution",
                        "file": filename,
                    }
                )

            # Insecure deserialization
            if any(keyword in patch for keyword in ["pickle.loads", "yaml.load", "unserialize"]):
                findings.append(
                    {
                        "severity": "high",
                        "category": "deserialization",
                        "message": "Potential insecure deserialization",
                        "file": filename,
                    }
                )

            security_findings.extend(findings)

        # Calculate risk score
        critical_count = sum(1 for f in security_findings if f["severity"] == "critical")
        high_count = sum(1 for f in security_findings if f["severity"] == "high")
        risk_score = (critical_count * 10) + (high_count * 5)

        return {
            "success": True,
            "findings": security_findings,
            "summary": {
                "total_findings": len(security_findings),
                "critical": critical_count,
                "high": high_count,
                "risk_score": min(risk_score, 100),
                "risk_level": "critical"
                if risk_score >= 30
                else "high"
                if risk_score >= 15
                else "medium"
                if risk_score > 0
                else "low",
            },
        }

    except Exception as e:
        logger.error(f"Failed to analyze PR security: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_get_file_content(
    owner: str,
    repo: str,
    path: str,
    repo_path: str | None = None,
    ref: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get file content from a cloned local repository (preferred) or GitHub API (fallback).

    When repo_path is provided (from internal_git_clone_repo), reads directly from the
    local filesystem — faster, works with private repos, and avoids GitHub API rate limits.

    Args:
        owner: Repository owner (used only for GitHub API fallback)
        repo: Repository name (used only for GitHub API fallback)
        path: File path relative to repository root
        repo_path: Local path to the cloned repository (from internal_git_clone_repo)
        ref: Branch/tag/SHA for GitHub API fallback (ignored when repo_path is set)
        config: Configuration dictionary
        runtime_context: Runtime context for authentication

    Returns:
        Dictionary with file content
    """
    # --- Local/remote filesystem read (preferred when repo is cloned) ---
    if repo_path:
        try:
            import os

            from src.services.compute.resolver import get_compute_session_from_config

            full_path = os.path.join(repo_path, path)
            _cs = await get_compute_session_from_config(config)

            if _cs is not None and _cs.is_remote:
                # Path traversal guard: simple prefix check (sandbox enforces it server-side)
                if not (full_path.startswith(repo_path + "/") or full_path == repo_path):
                    return {"success": False, "error": f"Path '{path}' is outside the repository directory"}

                # Check existence + type
                list_result = await _cs.list_dir(full_path)
                if list_result.get("success"):
                    # It's a directory (sandbox returns is_dir: bool)
                    raw = list_result.get("entries", [])
                    entries = [
                        {
                            "name": e.get("name", ""),
                            "type": "dir" if e.get("is_dir") else "file",
                            "path": os.path.join(path, e.get("name", "")),
                            "size": e.get("size", 0),
                        }
                        for e in sorted(raw, key=lambda e: (not e.get("is_dir"), e.get("name", "")))
                    ]
                    return {"success": True, "type": "directory", "path": path, "contents": entries}

                # Not a directory — try to read as file
                read_result = await _cs.read_file(full_path, max_lines=10000)
                if not read_result.get("success"):
                    return {"success": False, "error": f"Path '{path}' not found in repository"}
                content = read_result.get("content", "")
                return {"success": True, "type": "file", "content": content, "path": path, "size": len(content)}

            # --- Local read ---
            real_repo = os.path.realpath(repo_path)
            real_full = os.path.realpath(full_path)
            if not real_full.startswith(real_repo + os.sep) and real_full != real_repo:
                return {"success": False, "error": f"Path '{path}' is outside the repository directory"}

            if not os.path.exists(real_full):
                return {"success": False, "error": f"Path '{path}' not found in repository"}

            if os.path.isdir(real_full):
                entries = []
                for entry in sorted(os.scandir(real_full), key=lambda e: (not e.is_dir(), e.name)):
                    entries.append(
                        {
                            "name": entry.name,
                            "type": "dir" if entry.is_dir() else "file",
                            "path": os.path.relpath(entry.path, repo_path),
                            "size": entry.stat().st_size if entry.is_file() else 0,
                        }
                    )
                return {"success": True, "type": "directory", "path": path, "contents": entries}

            file_size = os.path.getsize(real_full)
            if file_size > 5 * 1024 * 1024:  # 5 MB guard
                return {"success": False, "error": f"File '{path}' is too large ({file_size // 1024}KB) to read"}

            with open(real_full, encoding="utf-8", errors="replace") as f:
                content = f.read()

            return {"success": True, "type": "file", "content": content, "path": path, "size": file_size}
        except Exception as e:
            logger.error(f"Failed to read file from local repo: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # --- GitHub API fallback (when no local clone available) ---
    try:
        token = await _get_github_token(runtime_context, config, owner=owner, repo=repo)

        params = {}
        if ref:
            params["ref"] = ref

        result = await _make_github_request("GET", f"/repos/{owner}/{repo}/contents/{path}", token, params=params)

        # GitHub returns a list when path is a directory
        if isinstance(result, list):
            return {
                "success": True,
                "type": "directory",
                "path": path,
                "contents": [
                    {
                        "name": item["name"],
                        "type": item["type"],
                        "path": item["path"],
                        "size": item.get("size", 0),
                    }
                    for item in result
                ],
            }

        # Decode base64 content for files
        content = base64.b64decode(result["content"]).decode("utf-8")

        return {
            "success": True,
            "type": "file",
            "content": content,
            "path": result["path"],
            "sha": result["sha"],
            "size": result["size"],
            "url": result["html_url"],
        }

    except Exception as e:
        err_str = str(e)
        if "404" in err_str or "Not Found" in err_str:
            logger.warning(f"File not found via GitHub API: {e}")
        else:
            logger.warning(f"Failed to get file content via GitHub API: {e}", exc_info=True)
        return {"success": False, "error": err_str}
