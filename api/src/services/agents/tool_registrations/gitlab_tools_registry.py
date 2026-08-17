"""
GitLab Tools Registry

Registers GitLab tools with the ADK tool registry.
Requires OAuth or API token configuration via IntegrationConfig.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_gitlab_tools(registry):
    """
    Register all GitLab tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.gitlab_tools import (
        internal_gitlab_approve_mr,
        internal_gitlab_clone_repo,
        internal_gitlab_close_issue,
        internal_gitlab_close_mr,
        internal_gitlab_create_branch,
        internal_gitlab_create_file,
        internal_gitlab_create_issue,
        internal_gitlab_create_merge_request,
        internal_gitlab_delete_file,
        internal_gitlab_get_file,
        internal_gitlab_get_issue,
        internal_gitlab_get_merge_request,
        internal_gitlab_get_mr_diff,
        internal_gitlab_get_project,
        internal_gitlab_get_user,
        internal_gitlab_list_branches,
        internal_gitlab_list_issue_comments,
        internal_gitlab_list_issues,
        internal_gitlab_list_merge_requests,
        internal_gitlab_list_mr_comments,
        internal_gitlab_list_projects,
        internal_gitlab_merge_mr,
        internal_gitlab_post_issue_comment,
        internal_gitlab_post_mr_comment,
        internal_gitlab_reopen_issue,
        internal_gitlab_reopen_mr,
        internal_gitlab_search_users,
        internal_gitlab_unapprove_mr,
        internal_gitlab_update_file,
        internal_gitlab_update_issue,
        internal_gitlab_update_mr,
        internal_gitlab_update_note,
    )

    # Create wrappers that inject runtime_context

    async def internal_gitlab_get_user_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_get_user(runtime_context=runtime_context, config=config)

    async def internal_gitlab_list_projects_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_list_projects(
            owned=kwargs.get("owned", True),
            membership=kwargs.get("membership", False),
            search=kwargs.get("search"),
            per_page=kwargs.get("per_page", 20),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_get_project_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_get_project(
            project_id=kwargs.get("project_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_create_merge_request_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_create_merge_request(
            project_id=kwargs.get("project_id"),
            source_branch=kwargs.get("source_branch"),
            target_branch=kwargs.get("target_branch"),
            title=kwargs.get("title"),
            description=kwargs.get("description", ""),
            remove_source_branch=kwargs.get("remove_source_branch", False),
            squash=kwargs.get("squash", False),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_list_merge_requests_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_list_merge_requests(
            project_id=kwargs.get("project_id"),
            state=kwargs.get("state", "opened"),
            per_page=kwargs.get("per_page", 20),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_get_merge_request_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_get_merge_request(
            project_id=kwargs.get("project_id"),
            merge_request_iid=kwargs.get("merge_request_iid"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_list_issues_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_list_issues(
            project_id=kwargs.get("project_id"),
            state=kwargs.get("state", "opened"),
            labels=kwargs.get("labels"),
            per_page=kwargs.get("per_page", 20),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_create_issue_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_create_issue(
            project_id=kwargs.get("project_id"),
            title=kwargs.get("title"),
            description=kwargs.get("description", ""),
            labels=kwargs.get("labels"),
            assignee_ids=kwargs.get("assignee_ids"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_list_branches_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_list_branches(
            project_id=kwargs.get("project_id"),
            search=kwargs.get("search"),
            per_page=kwargs.get("per_page", 20),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_create_branch_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_create_branch(
            project_id=kwargs.get("project_id"),
            branch_name=kwargs.get("branch_name"),
            ref=kwargs.get("ref", "main"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_create_file_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_create_file(
            project_id=kwargs.get("project_id"),
            file_path=kwargs.get("file_path"),
            content=kwargs.get("content"),
            commit_message=kwargs.get("commit_message"),
            branch=kwargs.get("branch", "main"),
            encoding=kwargs.get("encoding", "text"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_update_file_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_update_file(
            project_id=kwargs.get("project_id"),
            file_path=kwargs.get("file_path"),
            content=kwargs.get("content"),
            commit_message=kwargs.get("commit_message"),
            branch=kwargs.get("branch", "main"),
            encoding=kwargs.get("encoding", "text"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_delete_file_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_delete_file(
            project_id=kwargs.get("project_id"),
            file_path=kwargs.get("file_path"),
            commit_message=kwargs.get("commit_message"),
            branch=kwargs.get("branch", "main"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_get_file_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_get_file(
            project_id=kwargs.get("project_id"),
            file_path=kwargs.get("file_path"),
            ref=kwargs.get("ref", "main"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_clone_repo_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_clone_repo(
            repo_url=kwargs.get("repo_url"),
            use_ssh=kwargs.get("use_ssh", False),
            depth=kwargs.get("depth", 1),
            branch=kwargs.get("branch"),
            runtime_context=runtime_context,
            config=config,
        )

    # Register tools

    registry.register_tool(
        name="internal_gitlab_get_user",
        description="Get the authenticated GitLab user's profile information.",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        function=internal_gitlab_get_user_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_list_projects",
        description="List GitLab projects accessible to the authenticated user. Can filter by owned projects, membership, or search term.",
        parameters={
            "type": "object",
            "properties": {
                "owned": {
                    "type": "boolean",
                    "description": "Only show projects owned by user (default: true)",
                    "default": True,
                },
                "membership": {
                    "type": "boolean",
                    "description": "Only show projects where user is a member",
                    "default": False,
                },
                "search": {
                    "type": "string",
                    "description": "Search term to filter projects",
                },
                "per_page": {
                    "type": "integer",
                    "description": "Number of projects per page (max 100, default: 20)",
                    "default": 20,
                },
            },
            "required": [],
        },
        function=internal_gitlab_list_projects_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_get_project",
        description="Get detailed information about a GitLab project including URLs, branches, and statistics.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID (number) or URL-encoded path (e.g., 'namespace/project')",
                },
            },
            "required": ["project_id"],
        },
        function=internal_gitlab_get_project_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_create_merge_request",
        description="Create a merge request (MR) in a GitLab project to merge changes from one branch to another.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID or URL-encoded path",
                },
                "source_branch": {
                    "type": "string",
                    "description": "Branch containing the changes",
                },
                "target_branch": {
                    "type": "string",
                    "description": "Branch to merge into (e.g., 'main')",
                },
                "title": {
                    "type": "string",
                    "description": "Merge request title",
                },
                "description": {
                    "type": "string",
                    "description": "Merge request description (markdown supported)",
                    "default": "",
                },
                "remove_source_branch": {
                    "type": "boolean",
                    "description": "Delete source branch after merge",
                    "default": False,
                },
                "squash": {
                    "type": "boolean",
                    "description": "Squash commits on merge",
                    "default": False,
                },
            },
            "required": ["project_id", "source_branch", "target_branch", "title"],
        },
        function=internal_gitlab_create_merge_request_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_list_merge_requests",
        description="List merge requests for a GitLab project. Filter by state (opened, closed, merged, all).",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID or URL-encoded path",
                },
                "state": {
                    "type": "string",
                    "enum": ["opened", "closed", "merged", "all"],
                    "description": "Filter by merge request state (default: opened)",
                    "default": "opened",
                },
                "per_page": {
                    "type": "integer",
                    "description": "Number of MRs per page (max 100, default: 20)",
                    "default": 20,
                },
            },
            "required": ["project_id"],
        },
        function=internal_gitlab_list_merge_requests_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_get_merge_request",
        description="Get detailed information about a specific merge request including status, conflicts, and changes.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID or URL-encoded path",
                },
                "merge_request_iid": {
                    "type": "integer",
                    "description": "Merge request internal ID (IID, the number shown as !123)",
                },
            },
            "required": ["project_id", "merge_request_iid"],
        },
        function=internal_gitlab_get_merge_request_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_list_issues",
        description="List issues for a GitLab project. Filter by state or labels.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID or URL-encoded path",
                },
                "state": {
                    "type": "string",
                    "enum": ["opened", "closed", "all"],
                    "description": "Filter by issue state (default: opened)",
                    "default": "opened",
                },
                "labels": {
                    "type": "string",
                    "description": "Comma-separated list of label names to filter by",
                },
                "per_page": {
                    "type": "integer",
                    "description": "Number of issues per page (max 100, default: 20)",
                    "default": 20,
                },
            },
            "required": ["project_id"],
        },
        function=internal_gitlab_list_issues_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_create_issue",
        description="Create a new issue in a GitLab project.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID or URL-encoded path",
                },
                "title": {
                    "type": "string",
                    "description": "Issue title",
                },
                "description": {
                    "type": "string",
                    "description": "Issue description (markdown supported)",
                    "default": "",
                },
                "labels": {
                    "type": "string",
                    "description": "Comma-separated list of label names",
                },
                "assignee_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of user IDs to assign to the issue",
                },
            },
            "required": ["project_id", "title"],
        },
        function=internal_gitlab_create_issue_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_list_branches",
        description="List branches in a GitLab project repository.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID or URL-encoded path",
                },
                "search": {
                    "type": "string",
                    "description": "Search term to filter branches",
                },
                "per_page": {
                    "type": "integer",
                    "description": "Number of branches per page (max 100, default: 20)",
                    "default": 20,
                },
            },
            "required": ["project_id"],
        },
        function=internal_gitlab_list_branches_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_create_branch",
        description="Create a new branch in a GitLab project repository. Use this to create feature branches before making changes.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID or URL-encoded path",
                },
                "branch_name": {
                    "type": "string",
                    "description": "Name of the new branch to create",
                },
                "ref": {
                    "type": "string",
                    "description": "Source branch, tag, or commit SHA to create branch from (default: 'main')",
                    "default": "main",
                },
            },
            "required": ["project_id", "branch_name"],
        },
        function=internal_gitlab_create_branch_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_create_file",
        description="Create a new file in a GitLab repository and commit it. Use this to add new files to a repository.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID or URL-encoded path",
                },
                "file_path": {
                    "type": "string",
                    "description": "Path for the new file in the repository (e.g., 'src/new_file.py')",
                },
                "content": {
                    "type": "string",
                    "description": "Content of the file",
                },
                "commit_message": {
                    "type": "string",
                    "description": "Commit message for this change",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch to create the file in (default: 'main')",
                    "default": "main",
                },
                "encoding": {
                    "type": "string",
                    "enum": ["text", "base64"],
                    "description": "Content encoding - 'text' for plain text or 'base64' for binary files",
                    "default": "text",
                },
            },
            "required": ["project_id", "file_path", "content", "commit_message"],
        },
        function=internal_gitlab_create_file_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_update_file",
        description="Update an existing file in a GitLab repository and commit the changes. Use this to modify existing files.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID or URL-encoded path",
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to the file in the repository (e.g., 'src/main.py')",
                },
                "content": {
                    "type": "string",
                    "description": "New content for the file",
                },
                "commit_message": {
                    "type": "string",
                    "description": "Commit message for this change",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch containing the file (default: 'main')",
                    "default": "main",
                },
                "encoding": {
                    "type": "string",
                    "enum": ["text", "base64"],
                    "description": "Content encoding - 'text' for plain text or 'base64' for binary files",
                    "default": "text",
                },
            },
            "required": ["project_id", "file_path", "content", "commit_message"],
        },
        function=internal_gitlab_update_file_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_delete_file",
        description="Delete a file from a GitLab repository and commit the deletion.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID or URL-encoded path",
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to delete (e.g., 'src/old_file.py')",
                },
                "commit_message": {
                    "type": "string",
                    "description": "Commit message for this deletion",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch containing the file (default: 'main')",
                    "default": "main",
                },
            },
            "required": ["project_id", "file_path", "commit_message"],
        },
        function=internal_gitlab_delete_file_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_get_file",
        description="Get a file's content from a GitLab repository.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Project ID or URL-encoded path",
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to the file in the repository (e.g., 'src/main.py')",
                },
                "ref": {
                    "type": "string",
                    "description": "Branch, tag, or commit SHA (default: 'main')",
                    "default": "main",
                },
            },
            "required": ["project_id", "file_path"],
        },
        function=internal_gitlab_get_file_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_clone_repo",
        description=(
            "Clone a GitLab repository into a temporary directory. Automatically authenticates using the "
            "configured GitLab token. Returns the path to the cloned repository. After cloning, use "
            "internal_git_* tools (create_branch, commit_and_push, etc.) for local operations. Defaults to a "
            "shallow, single-branch clone (fast and reliable even for large repos); pass a 'branch' to clone "
            "a specific branch directly, or 'depth: 0' for a full clone with complete history."
        ),
        parameters={
            "type": "object",
            "properties": {
                "repo_url": {
                    "type": "string",
                    "description": "GitLab repository URL (HTTPS or SSH format)",
                },
                "use_ssh": {
                    "type": "boolean",
                    "description": "Whether to convert HTTPS URLs to SSH (default: false, uses token authentication)",
                    "default": False,
                },
                "depth": {
                    "type": "integer",
                    "description": (
                        "Number of commits of history to fetch. Default 1 (shallow clone, recommended for "
                        "most tasks). Use 0 for a full clone with complete history."
                    ),
                    "default": 1,
                },
                "branch": {
                    "type": "string",
                    "description": "Specific branch to clone directly. Omit to clone the repository's default branch.",
                },
            },
            "required": ["repo_url"],
        },
        function=internal_gitlab_clone_repo_wrapper,
    )

    # Additional wrappers for new tools

    async def internal_gitlab_post_mr_comment_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_post_mr_comment(
            project_id=kwargs.get("project_id"),
            merge_request_iid=kwargs.get("merge_request_iid"),
            body=kwargs.get("body"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_post_issue_comment_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_post_issue_comment(
            project_id=kwargs.get("project_id"),
            issue_iid=kwargs.get("issue_iid"),
            body=kwargs.get("body"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_update_note_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_update_note(
            project_id=kwargs.get("project_id"),
            noteable_type=kwargs.get("noteable_type"),
            noteable_iid=kwargs.get("noteable_iid"),
            note_id=kwargs.get("note_id"),
            body=kwargs.get("body"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_list_mr_comments_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_list_mr_comments(
            project_id=kwargs.get("project_id"),
            merge_request_iid=kwargs.get("merge_request_iid"),
            per_page=kwargs.get("per_page", 20),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_list_issue_comments_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_list_issue_comments(
            project_id=kwargs.get("project_id"),
            issue_iid=kwargs.get("issue_iid"),
            per_page=kwargs.get("per_page", 20),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_merge_mr_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_merge_mr(
            project_id=kwargs.get("project_id"),
            merge_request_iid=kwargs.get("merge_request_iid"),
            squash=kwargs.get("squash", False),
            should_remove_source_branch=kwargs.get("should_remove_source_branch", False),
            merge_commit_message=kwargs.get("merge_commit_message"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_close_mr_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_close_mr(
            project_id=kwargs.get("project_id"),
            merge_request_iid=kwargs.get("merge_request_iid"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_reopen_mr_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_reopen_mr(
            project_id=kwargs.get("project_id"),
            merge_request_iid=kwargs.get("merge_request_iid"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_approve_mr_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_approve_mr(
            project_id=kwargs.get("project_id"),
            merge_request_iid=kwargs.get("merge_request_iid"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_unapprove_mr_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_unapprove_mr(
            project_id=kwargs.get("project_id"),
            merge_request_iid=kwargs.get("merge_request_iid"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_update_mr_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_update_mr(
            project_id=kwargs.get("project_id"),
            merge_request_iid=kwargs.get("merge_request_iid"),
            title=kwargs.get("title"),
            description=kwargs.get("description"),
            target_branch=kwargs.get("target_branch"),
            labels=kwargs.get("labels"),
            assignee_ids=kwargs.get("assignee_ids"),
            reviewer_ids=kwargs.get("reviewer_ids"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_get_issue_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_get_issue(
            project_id=kwargs.get("project_id"),
            issue_iid=kwargs.get("issue_iid"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_update_issue_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_update_issue(
            project_id=kwargs.get("project_id"),
            issue_iid=kwargs.get("issue_iid"),
            title=kwargs.get("title"),
            description=kwargs.get("description"),
            labels=kwargs.get("labels"),
            assignee_ids=kwargs.get("assignee_ids"),
            milestone_id=kwargs.get("milestone_id"),
            state_event=kwargs.get("state_event"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_close_issue_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_close_issue(
            project_id=kwargs.get("project_id"),
            issue_iid=kwargs.get("issue_iid"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_reopen_issue_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_reopen_issue(
            project_id=kwargs.get("project_id"),
            issue_iid=kwargs.get("issue_iid"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_search_users_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_search_users(
            project_id=kwargs.get("project_id"),
            search=kwargs.get("search"),
            per_page=kwargs.get("per_page", 20),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_gitlab_get_mr_diff_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_gitlab_get_mr_diff(
            project_id=kwargs.get("project_id"),
            merge_request_iid=kwargs.get("merge_request_iid"),
            runtime_context=runtime_context,
            config=config,
        )

    # Register new tools

    registry.register_tool(
        name="internal_gitlab_post_mr_comment",
        description="Post a comment (note) on a GitLab merge request.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "merge_request_iid": {"type": "integer", "description": "Merge request internal ID (IID)"},
                "body": {"type": "string", "description": "Comment body (markdown supported)"},
            },
            "required": ["project_id", "merge_request_iid", "body"],
        },
        function=internal_gitlab_post_mr_comment_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_post_issue_comment",
        description="Post a comment (note) on a GitLab issue.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "issue_iid": {"type": "integer", "description": "Issue internal ID (IID)"},
                "body": {"type": "string", "description": "Comment body (markdown supported)"},
            },
            "required": ["project_id", "issue_iid", "body"],
        },
        function=internal_gitlab_post_issue_comment_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_update_note",
        description="Update a comment (note) on a GitLab merge request or issue.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "noteable_type": {
                    "type": "string",
                    "enum": ["merge_requests", "issues"],
                    "description": "Type: 'merge_requests' or 'issues'",
                },
                "noteable_iid": {"type": "integer", "description": "MR or issue internal ID (IID)"},
                "note_id": {"type": "integer", "description": "Note ID to update"},
                "body": {"type": "string", "description": "New comment body"},
            },
            "required": ["project_id", "noteable_type", "noteable_iid", "note_id", "body"],
        },
        function=internal_gitlab_update_note_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_list_mr_comments",
        description="List comments (notes) on a GitLab merge request.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "merge_request_iid": {"type": "integer", "description": "Merge request internal ID (IID)"},
                "per_page": {"type": "integer", "description": "Number per page (max 100)", "default": 20},
            },
            "required": ["project_id", "merge_request_iid"],
        },
        function=internal_gitlab_list_mr_comments_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_list_issue_comments",
        description="List comments (notes) on a GitLab issue.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "issue_iid": {"type": "integer", "description": "Issue internal ID (IID)"},
                "per_page": {"type": "integer", "description": "Number per page (max 100)", "default": 20},
            },
            "required": ["project_id", "issue_iid"],
        },
        function=internal_gitlab_list_issue_comments_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_merge_mr",
        description="Merge a GitLab merge request.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "merge_request_iid": {"type": "integer", "description": "Merge request internal ID (IID)"},
                "squash": {"type": "boolean", "description": "Squash commits", "default": False},
                "should_remove_source_branch": {
                    "type": "boolean",
                    "description": "Remove source branch after merge",
                    "default": False,
                },
                "merge_commit_message": {"type": "string", "description": "Custom merge commit message"},
            },
            "required": ["project_id", "merge_request_iid"],
        },
        function=internal_gitlab_merge_mr_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_close_mr",
        description="Close a GitLab merge request without merging.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "merge_request_iid": {"type": "integer", "description": "Merge request internal ID (IID)"},
            },
            "required": ["project_id", "merge_request_iid"],
        },
        function=internal_gitlab_close_mr_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_reopen_mr",
        description="Reopen a closed GitLab merge request.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "merge_request_iid": {"type": "integer", "description": "Merge request internal ID (IID)"},
            },
            "required": ["project_id", "merge_request_iid"],
        },
        function=internal_gitlab_reopen_mr_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_approve_mr",
        description="Approve a GitLab merge request.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "merge_request_iid": {"type": "integer", "description": "Merge request internal ID (IID)"},
            },
            "required": ["project_id", "merge_request_iid"],
        },
        function=internal_gitlab_approve_mr_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_unapprove_mr",
        description="Unapprove (revoke approval) of a GitLab merge request.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "merge_request_iid": {"type": "integer", "description": "Merge request internal ID (IID)"},
            },
            "required": ["project_id", "merge_request_iid"],
        },
        function=internal_gitlab_unapprove_mr_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_update_mr",
        description="Update a GitLab merge request.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "merge_request_iid": {"type": "integer", "description": "Merge request internal ID (IID)"},
                "title": {"type": "string", "description": "New title"},
                "description": {"type": "string", "description": "New description"},
                "target_branch": {"type": "string", "description": "New target branch"},
                "labels": {"type": "string", "description": "Comma-separated list of labels"},
                "assignee_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of user IDs to assign",
                },
                "reviewer_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of user IDs to request review",
                },
            },
            "required": ["project_id", "merge_request_iid"],
        },
        function=internal_gitlab_update_mr_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_get_issue",
        description="Get details of a specific GitLab issue.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "issue_iid": {"type": "integer", "description": "Issue internal ID (IID)"},
            },
            "required": ["project_id", "issue_iid"],
        },
        function=internal_gitlab_get_issue_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_update_issue",
        description="Update a GitLab issue.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "issue_iid": {"type": "integer", "description": "Issue internal ID (IID)"},
                "title": {"type": "string", "description": "New title"},
                "description": {"type": "string", "description": "New description"},
                "labels": {"type": "string", "description": "Comma-separated list of labels"},
                "assignee_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of user IDs to assign",
                },
                "milestone_id": {"type": "integer", "description": "Milestone ID (0 to remove)"},
                "state_event": {
                    "type": "string",
                    "enum": ["close", "reopen"],
                    "description": "State event: 'close' or 'reopen'",
                },
            },
            "required": ["project_id", "issue_iid"],
        },
        function=internal_gitlab_update_issue_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_close_issue",
        description="Close a GitLab issue.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "issue_iid": {"type": "integer", "description": "Issue internal ID (IID)"},
            },
            "required": ["project_id", "issue_iid"],
        },
        function=internal_gitlab_close_issue_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_reopen_issue",
        description="Reopen a closed GitLab issue.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "issue_iid": {"type": "integer", "description": "Issue internal ID (IID)"},
            },
            "required": ["project_id", "issue_iid"],
        },
        function=internal_gitlab_reopen_issue_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_search_users",
        description="Search for users in a GitLab project (members).",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "search": {"type": "string", "description": "Search term (username or name)"},
                "per_page": {"type": "integer", "description": "Number per page (max 100)", "default": 20},
            },
            "required": ["project_id", "search"],
        },
        function=internal_gitlab_search_users_wrapper,
    )

    registry.register_tool(
        name="internal_gitlab_get_mr_diff",
        description="Get the diff (changes) of a GitLab merge request.",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID or URL-encoded path"},
                "merge_request_iid": {"type": "integer", "description": "Merge request internal ID (IID)"},
            },
            "required": ["project_id", "merge_request_iid"],
        },
        function=internal_gitlab_get_mr_diff_wrapper,
    )

    logger.info("Registered 32 GitLab tools")
