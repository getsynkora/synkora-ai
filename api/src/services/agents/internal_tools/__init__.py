"""
Internal Tools for Synkora Agents.


Built-in tools that are available by default without requiring external MCP servers.
All internal tools are prefixed with "internal_" to distinguish them from MCP and custom tools.
"""

from src.services.agents.internal_tools.command_tools import internal_run_command
from src.services.agents.internal_tools.data_pipeline_tools import query_database_to_s3
from src.services.agents.internal_tools.database_tools import (
    internal_generate_chart,
    internal_get_database_schema,
    internal_list_database_connections,
    internal_query_and_chart,
    internal_query_database,
)

# Diagram tools
from src.services.agents.internal_tools.diagram_tools import (
    internal_generate_diagram,
    internal_generate_quick_diagram,
)
from src.services.agents.internal_tools.elasticsearch_tools import (
    internal_elasticsearch_get_index_stats,
    internal_elasticsearch_list_indices,
    internal_elasticsearch_search,
)
from src.services.agents.internal_tools.file_tools import (
    internal_create_directory,
    internal_directory_tree,
    internal_edit_file,
    internal_get_file_info,
    internal_glob,
    internal_grep,
    internal_list_directory,
    internal_move_file,
    internal_notebook_edit,
    internal_read_file,
    internal_search_files,
    internal_write_file,
)
from src.services.agents.internal_tools.git_branch_tools import (
    internal_git_create_branch,
    internal_git_list_branches,
    internal_git_pull_changes,
    internal_git_switch_branch,
)
from src.services.agents.internal_tools.git_commit_tools import (
    internal_git_cherry_pick,
    internal_git_commit_and_push,
    internal_git_get_commit_history,
    internal_git_get_diff,
    internal_git_get_status,
    internal_git_revert_commit,
)
from src.services.agents.internal_tools.git_repo_tools import (
    internal_git_add_remote,
    internal_git_cleanup_repo,
    internal_git_clone_repo,
)

# GitLab tools
from src.services.agents.internal_tools.gitlab_tools import (
    internal_gitlab_clone_repo,
    internal_gitlab_create_issue,
    internal_gitlab_create_merge_request,
    internal_gitlab_get_file,
    internal_gitlab_get_merge_request,
    internal_gitlab_get_project,
    internal_gitlab_get_user,
    internal_gitlab_list_branches,
    internal_gitlab_list_issues,
    internal_gitlab_list_merge_requests,
    internal_gitlab_list_projects,
)

# Hacker News tools
from src.services.agents.internal_tools.hackernews_tools import (
    internal_hackernews_get_ask_hn,
    internal_hackernews_get_best_stories,
    internal_hackernews_get_new_stories,
    internal_hackernews_get_show_hn,
    internal_hackernews_get_story_details,
    internal_hackernews_get_top_stories,
    internal_hackernews_get_trending_topics,
    internal_hackernews_get_user,
    internal_hackernews_search,
)

# KB ingest tools
from src.services.agents.internal_tools.kb_ingest_tools import (
    internal_kb_add_text,
    internal_kb_crawl_url,
)

# LinkedIn tools
from src.services.agents.internal_tools.linkedin_tools import (
    internal_linkedin_get_company_info,
    internal_linkedin_get_posts,
    internal_linkedin_get_profile,
    internal_linkedin_post_text,
    internal_linkedin_post_with_image,
    internal_linkedin_share_url,
)

# News tools (NewsAPI + RSS)
from src.services.agents.internal_tools.news_tools import (
    internal_fetch_rss_feed,
    internal_news_search,
)

# Recall.ai meeting bot tools
from src.services.agents.internal_tools.recall_tools import (
    internal_recall_get_bot_status,
    internal_recall_get_recording,
    internal_recall_get_transcript,
    internal_recall_list_bots,
    internal_recall_remove_bot,
    internal_recall_send_bot,
    internal_recall_summarize_meeting,
)
from src.services.agents.internal_tools.role_tools import (
    internal_check_escalation_status,
    internal_escalate_to_human,
    internal_get_my_human_contact,
    internal_get_my_role,
    internal_get_pending_escalations,
    internal_get_project_agents,
    internal_get_project_context,
    internal_get_project_info,
    internal_update_project_context,
)
from src.services.agents.internal_tools.slack_tools import (
    internal_slack_add_reaction,
    internal_slack_join_channel,
    internal_slack_list_channels,
    internal_slack_read_channel_messages,
    internal_slack_read_thread,
    internal_slack_search_messages,
    internal_slack_send_message,
)

# Spawn agent tools
from src.services.agents.internal_tools.spawn_agent_tool import (
    internal_check_task,
    internal_list_background_tasks,
    internal_spawn_agent,
)
from src.services.agents.internal_tools.storage_tools import (
    internal_s3_delete_file,
    internal_s3_download_file,
    internal_s3_file_exists,
    internal_s3_generate_presigned_url,
    internal_s3_get_file_metadata,
    internal_s3_list_files,
    internal_s3_upload_directory,
    internal_s3_upload_file,
)
from src.services.agents.internal_tools.tutorial_generator import (
    internal_analyze_relationships,
    internal_combine_tutorial,
    internal_fetch_repository_files,
    internal_generate_tutorial_chapter,
    internal_identify_abstractions,
    internal_order_chapters,
)

# Twitter tools
from src.services.agents.internal_tools.twitter_tools import (
    internal_twitter_delete_tweet,
    internal_twitter_get_bookmarks,
    internal_twitter_get_my_profile,
    internal_twitter_get_user_by_username,
    internal_twitter_get_user_timeline,
    internal_twitter_post_tweet,
    internal_twitter_search_tweets,
)

# Web tools
from src.services.agents.internal_tools.web_tools import (
    internal_web_fetch,
)

# YouTube tools
from src.services.agents.internal_tools.youtube_tools import (
    internal_youtube_get_transcript,
    internal_youtube_get_transcript_segment,
    internal_youtube_list_transcript_languages,
)
from src.services.agents.internal_tools.zoom_tools import (
    internal_zoom_create_meeting,
    internal_zoom_delete_meeting,
    internal_zoom_get_meeting,
    internal_zoom_get_meeting_recordings,
    internal_zoom_list_meetings,
    internal_zoom_update_meeting,
)

__all__ = [
    "internal_read_file",
    "internal_search_files",
    "internal_write_file",
    "internal_edit_file",
    "internal_get_file_info",
    "internal_move_file",
    "internal_create_directory",
    "internal_list_directory",
    "internal_directory_tree",
    "internal_glob",
    "internal_grep",
    "internal_notebook_edit",
    "internal_web_fetch",
    "internal_run_command",
    # Git repo tools
    "internal_git_clone_repo",
    "internal_git_add_remote",
    "internal_git_cleanup_repo",
    # Git branch tools
    "internal_git_create_branch",
    "internal_git_switch_branch",
    "internal_git_list_branches",
    "internal_git_pull_changes",
    # Git commit tools
    "internal_git_get_status",
    "internal_git_get_diff",
    "internal_git_commit_and_push",
    "internal_git_get_commit_history",
    "internal_git_cherry_pick",
    "internal_git_revert_commit",
    "internal_query_database",
    "internal_list_database_connections",
    "internal_get_database_schema",
    "internal_generate_chart",
    "internal_query_and_chart",
    "query_database_to_s3",
    "internal_fetch_repository_files",
    "internal_identify_abstractions",
    "internal_analyze_relationships",
    "internal_order_chapters",
    "internal_generate_tutorial_chapter",
    "internal_combine_tutorial",
    "internal_s3_upload_file",
    "internal_s3_upload_directory",
    "internal_s3_download_file",
    "internal_s3_generate_presigned_url",
    "internal_s3_list_files",
    "internal_s3_delete_file",
    "internal_s3_file_exists",
    "internal_s3_get_file_metadata",
    "internal_zoom_create_meeting",
    "internal_zoom_list_meetings",
    "internal_zoom_get_meeting",
    "internal_zoom_update_meeting",
    "internal_zoom_delete_meeting",
    "internal_zoom_get_meeting_recordings",
    "internal_slack_list_channels",
    "internal_slack_read_channel_messages",
    "internal_slack_read_thread",
    "internal_slack_send_message",
    "internal_slack_join_channel",
    "internal_slack_search_messages",
    "internal_slack_add_reaction",
    "internal_elasticsearch_search",
    "internal_elasticsearch_list_indices",
    "internal_elasticsearch_get_index_stats",
    # Role tools
    "internal_get_project_info",
    "internal_get_project_context",
    "internal_update_project_context",
    "internal_escalate_to_human",
    "internal_get_my_human_contact",
    "internal_check_escalation_status",
    "internal_get_project_agents",
    "internal_get_my_role",
    "internal_get_pending_escalations",
    # YouTube tools
    "internal_youtube_get_transcript",
    "internal_youtube_list_transcript_languages",
    "internal_youtube_get_transcript_segment",
    # Twitter tools
    "internal_twitter_get_user_timeline",
    "internal_twitter_get_bookmarks",
    "internal_twitter_post_tweet",
    "internal_twitter_search_tweets",
    "internal_twitter_get_user_by_username",
    "internal_twitter_get_my_profile",
    "internal_twitter_delete_tweet",
    # LinkedIn tools
    "internal_linkedin_get_profile",
    "internal_linkedin_get_posts",
    "internal_linkedin_post_text",
    "internal_linkedin_share_url",
    "internal_linkedin_get_company_info",
    "internal_linkedin_post_with_image",
    # News tools (NewsAPI + RSS)
    "internal_news_search",
    "internal_fetch_rss_feed",
    # Hacker News tools
    "internal_hackernews_get_top_stories",
    "internal_hackernews_get_new_stories",
    "internal_hackernews_get_best_stories",
    "internal_hackernews_get_ask_hn",
    "internal_hackernews_get_show_hn",
    "internal_hackernews_get_story_details",
    "internal_hackernews_search",
    "internal_hackernews_get_user",
    "internal_hackernews_get_trending_topics",
    # GitLab tools
    "internal_gitlab_get_user",
    "internal_gitlab_list_projects",
    "internal_gitlab_get_project",
    "internal_gitlab_create_merge_request",
    "internal_gitlab_list_merge_requests",
    "internal_gitlab_get_merge_request",
    "internal_gitlab_list_issues",
    "internal_gitlab_create_issue",
    "internal_gitlab_list_branches",
    "internal_gitlab_get_file",
    "internal_gitlab_clone_repo",
    # Recall.ai meeting bot tools
    "internal_recall_send_bot",
    "internal_recall_get_bot_status",
    "internal_recall_list_bots",
    "internal_recall_get_transcript",
    "internal_recall_get_recording",
    "internal_recall_remove_bot",
    "internal_recall_summarize_meeting",
    # Spawn agent tools
    "internal_spawn_agent",
    "internal_check_task",
    "internal_list_background_tasks",
    # Diagram tools
    "internal_generate_diagram",
    "internal_generate_quick_diagram",
    # KB ingest tools
    "internal_kb_crawl_url",
    "internal_kb_add_text",
]
