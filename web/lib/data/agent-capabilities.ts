/**
 * Agent Capabilities Data Layer
 *
 * Defines capabilities that group related tools together for simplified agent creation.
 * Instead of selecting 50+ individual tools, users select 5-10 capabilities.
 */

export interface Capability {
  id: string;
  name: string;
  description: string;
  icon: string;
  toolPatterns: string[];  // Patterns to match tool names (e.g., 'internal_git_*')
  tools?: string[];        // Explicit tool names (populated at runtime from backend)
  requiresOAuth?: string[];  // OAuth providers needed (github, SLACK, etc.)
}

export interface AgentPreset {
  id: string;
  name: string;
  description: string;
  icon: string;
  capabilities: string[];  // Capability IDs
}

/**
 * Capability Definitions
 * Each capability groups related tools by pattern matching.
 */
export const CAPABILITIES: Capability[] = [
  {
    id: 'git-local',
    name: 'Git (Local)',
    description: 'Clone repos, manage branches, commit and push changes',
    icon: '🔀',
    toolPatterns: [
      'internal_git_*',
    ],
  },
  {
    id: 'github',
    name: 'GitHub',
    description: 'Manage issues, pull requests, code review, and repository info via GitHub API',
    icon: '🐙',
    toolPatterns: [
      'internal_github_*',
    ],
    requiresOAuth: ['github']
  },
  {
    id: 'project-mgmt',
    name: 'Project Management',
    description: 'Manage Jira issues, ClickUp tasks, comments, and workflows',
    icon: '📋',
    toolPatterns: [
      'internal_jira_*',
      'internal_clickup_*'
    ],
    requiresOAuth: ['jira', 'clickup']
  },
  {
    id: 'communication',
    name: 'Slack',
    description: 'Send messages, search conversations, manage channels',
    icon: '💬',
    toolPatterns: [
      'internal_slack_*',
      'internal_send_slack_*',
      'internal_search_slack_*'
    ],
    requiresOAuth: ['SLACK']
  },
  {
    id: 'meetings-calendar',
    name: 'Calendar & Zoom',
    description: 'Manage calendar events, schedule meetings, video conferencing',
    icon: '📅',
    toolPatterns: [
      'internal_zoom_*',
      'internal_google_calendar_*'
    ],
    requiresOAuth: ['zoom', 'google_calendar']
  },
  {
    id: 'files-storage',
    name: 'Files & Storage',
    description: 'Read, write, search files, manage cloud storage',
    icon: '📁',
    toolPatterns: [
      'internal_read_*_file',
      'internal_write_file',
      'internal_edit_file',
      'internal_search_files',
      'internal_get_file_info',
      'internal_move_file',
      'internal_create_directory',
      'internal_list_directory',
      'internal_directory_tree',
      'internal_s3_*',
      'internal_storage_*',
      'internal_google_drive_*'
    ],
    requiresOAuth: ['google_drive']
  },
  {
    id: 'database-analytics',
    name: 'Database & Analytics',
    description: 'Query databases, generate charts, Elasticsearch search',
    icon: '📊',
    toolPatterns: [
      'internal_query_*',
      'internal_list_database_*',
      'internal_get_database_*',
      'internal_generate_chart',
      'internal_elasticsearch_*',
      'internal_chart_*'
    ]
  },
  {
    id: 'image-generation',
    name: 'Image Generation',
    description: 'Generate AI images from text prompts (gpt-image-2, Imagen 3, Grok Aurora)',
    icon: '🎨',
    toolPatterns: ['internal_generate_image']
  },
  {
    id: 'documents',
    name: 'Documents',
    description: 'Generate PDFs, PowerPoints, Google Docs and Sheets',
    icon: '📄',
    toolPatterns: [
      'internal_generate_pdf',
      'internal_generate_powerpoint',
      'internal_generate_google_doc',
      'internal_generate_google_sheet',
      'internal_*_pdf',
      'internal_*_pptx',
      'internal_*_docx'
    ]
  },
  {
    id: 'social-media',
    name: 'Social Media',
    description: 'Post to Twitter, LinkedIn, search YouTube, Hacker News',
    icon: '📱',
    toolPatterns: [
      'internal_twitter_*',
      'internal_linkedin_*',
      'internal_youtube_*',
      'internal_hackernews_*',
      'internal_hn_*'
    ],
    requiresOAuth: ['twitter', 'linkedin']
  },
  {
    id: 'browser-web',
    name: 'Browser & Web',
    description: 'Web automation, screenshots, scraping, link extraction',
    icon: '🌐',
    toolPatterns: [
      'internal_browser_*',
      'internal_navigate_*',
      'internal_screenshot_*',
      'internal_extract_*',
      'internal_check_element*',
      'internal_scrape_*'
    ]
  },
  {
    id: 'system-commands',
    name: 'System & Commands',
    description: 'Execute system commands, manage processes',
    icon: '⚡',
    toolPatterns: [
      'internal_run_command',
      'internal_execute_*',
      'internal_process_*'
    ]
  },
  {
    id: 'passwords-secrets',
    name: 'Passwords & Secrets',
    description: 'Access 1Password vaults, retrieve credentials securely',
    icon: '🔐',
    toolPatterns: [
      'internal_1password_*',
      'internal_onepassword_*',
      'internal_op_*'
    ]
  },
  {
    id: 'email',
    name: 'Email',
    description: 'Send email, read inboxes, and handle OTP or magic-link flows via Gmail or Mailisk',
    icon: '✉️',
    toolPatterns: [
      'internal_email_*',
      'internal_gmail_*',
      'internal_mailisk_*',
      'internal_send_email',
      'internal_read_email*',
      'internal_search_email*'
    ],
    requiresOAuth: ['gmail', 'mailisk']
  },
  {
    id: 'meeting-recording',
    name: 'Meeting Recording',
    description: 'Record and transcribe meetings on Zoom, Meet, Teams, Slack',
    icon: '🎥',
    toolPatterns: [
      'internal_recall_*'
    ],
    requiresOAuth: ['recall']
  }
];

/**
 * Agent Presets
 * Pre-configured capability bundles for common use cases.
 */
export const AGENT_PRESETS: AgentPreset[] = [
  {
    id: 'all-purpose',
    name: 'All-Purpose Assistant',
    description: 'All capabilities enabled - most powerful agent',
    icon: '⭐',
    capabilities: CAPABILITIES.map(c => c.id)
  },
  {
    id: 'developer',
    name: 'Developer Assistant',
    description: 'Code, GitHub, Jira, Files, Commands',
    icon: '💻',
    capabilities: ['git-local', 'github', 'project-mgmt', 'files-storage', 'system-commands', 'database-analytics']
  },
  {
    id: 'content-creator',
    name: 'Content Creator',
    description: 'Social Media, Documents, Browser',
    icon: '📱',
    capabilities: ['social-media', 'documents', 'browser-web', 'files-storage']
  },
  {
    id: 'data-analyst',
    name: 'Data Analyst',
    description: 'Database, Charts, Documents, Files',
    icon: '📊',
    capabilities: ['database-analytics', 'documents', 'files-storage']
  },
  {
    id: 'project-manager',
    name: 'Project Manager',
    description: 'Project Management, Slack, Calendar, Documents',
    icon: '📋',
    capabilities: ['project-mgmt', 'communication', 'meetings-calendar', 'documents', 'email']
  }
];

/**
 * Match a tool name against a pattern.
 * Supports wildcard (*) at the end of patterns.
 */
export function matchToolPattern(toolName: string, pattern: string): boolean {
  // Handle wildcard patterns (e.g., 'internal_git_*')
  if (pattern.endsWith('*')) {
    const prefix = pattern.slice(0, -1);
    return toolName.startsWith(prefix);
  }
  // Exact match
  return toolName === pattern;
}

/**
 * Get all capabilities that include a specific tool.
 */
export function getCapabilitiesForTool(toolName: string): Capability[] {
  return CAPABILITIES.filter(capability =>
    capability.toolPatterns.some(pattern => matchToolPattern(toolName, pattern))
  );
}

/**
 * Get all tools that match a capability's patterns from a list of available tools.
 */
export function getToolsForCapability(capability: Capability, availableTools: string[]): string[] {
  return availableTools.filter(tool =>
    capability.toolPatterns.some(pattern => matchToolPattern(tool, pattern))
  );
}

/**
 * Get all tools for multiple capabilities.
 */
export function getToolsForCapabilities(capabilityIds: string[], availableTools: string[]): string[] {
  const capabilities = CAPABILITIES.filter(c => capabilityIds.includes(c.id));
  const toolSet = new Set<string>();

  capabilities.forEach(capability => {
    getToolsForCapability(capability, availableTools).forEach(tool => {
      toolSet.add(tool);
    });
  });

  return Array.from(toolSet);
}

/**
 * Get all required OAuth providers for selected capabilities.
 */
export function getRequiredOAuthProviders(capabilityIds: string[]): string[] {
  const capabilities = CAPABILITIES.filter(c => capabilityIds.includes(c.id));
  const providerSet = new Set<string>();

  capabilities.forEach(capability => {
    capability.requiresOAuth?.forEach(provider => {
      providerSet.add(provider);
    });
  });

  return Array.from(providerSet);
}

/**
 * Get a preset by ID.
 */
export function getPreset(presetId: string): AgentPreset | undefined {
  return AGENT_PRESETS.find(p => p.id === presetId);
}

/**
 * Get capabilities for a preset.
 */
export function getCapabilitiesForPreset(presetId: string): Capability[] {
  const preset = getPreset(presetId);
  if (!preset) return [];
  return CAPABILITIES.filter(c => preset.capabilities.includes(c.id));
}
