'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import {
  Settings,
  Search,
  Plus,
  Check,
  X,
  Eye,
  EyeOff,
  Save,
  TestTube,
  ArrowLeft,
  Github,
  Unlink,
  FileText,
  Database,
  Cloud,
  Terminal,
  MessageSquare,
  Calendar,
  Package,
  Info,
  ChevronDown,
  ChevronRight,
  Globe,
  ExternalLink,
  AlertTriangle,
  Link2,
  CheckCircle,
  Mail,
  Newspaper
} from 'lucide-react';
import Link from 'next/link';
import { apiClient } from '@/lib/api/client';
import { CapabilityToggles } from '@/components/agents/CapabilitySelector';
import AgentPageShell from '@/components/agents/AgentPageShell';

interface Tool {
  name: string;
  displayName: string;
  description: string;
  category: string;
  icon: string;
  requiredFields: ToolField[];
  optionalFields?: ToolField[];
  configurable?: boolean;
  oauthProvider?: string;
  integrationConfigType?: string;  // For tools that use integration configs (e.g., GMAIL for email)
}

interface ToolField {
  key: string;
  label: string;
  description: string;
  placeholder: string;
  type: 'text' | 'password' | 'number' | 'select' | 'textarea';
  options?: { value: string; label: string }[];
}

interface AgentTool {
  id: number;
  tool_name: string;
  config: Record<string, string>;
  enabled: boolean;
}

interface CustomTool {
  id: string;
  name: string;
  description: string;
  server_url: string;
  auth_type: string;
  enabled: boolean;
  icon?: string;
  tags?: string[];
  openapi_schema: any;
}

interface ToolGroup {
  id: string;
  name: string;
  description: string;
  icon: any;
  tools: Tool[];
  expanded?: boolean;
}

const toolModalShellClass =
  'w-full max-w-5xl overflow-hidden rounded-[2rem] border border-black/10 bg-[#fffdf8] shadow-[0_32px_90px_rgba(23,23,23,0.22)]';
const toolModalSectionClass =
  'rounded-[1.5rem] border border-black/8 bg-white p-5 shadow-[0_10px_30px_rgba(23,23,23,0.05)]';
const toolModalFieldClass =
  'w-full rounded-[1rem] border border-black/10 bg-[#fcfaf5] px-4 py-3 text-sm text-[#171717] outline-none transition focus:border-[#79dfbc] focus:ring-4 focus:ring-[#79dfbc]/20';
const toolModalLabelClass = 'mb-1.5 block text-sm font-semibold text-[#171717]';
const toolModalHelpClass = 'mb-2.5 text-xs leading-5 text-[#6d675f]';
const toolModalLinkClass = 'font-semibold text-[#d44a32] transition hover:text-[#b93d27]';

// Tool categories organized by integration/service (A–Z, Custom last)
const TOOL_GROUPS: ToolGroup[] = [
  {
    id: 'onepassword',
    name: '1Password',
    description: 'Read secrets, manage vaults, items, and generate passwords',
    icon: Package,
    tools: [],
    expanded: false
  },
  {
    id: 'agents',
    name: 'Agents',
    description: 'Spawn agents, transfer tasks, check roles, escalate to human, and manage multi-agent workflows',
    icon: Settings,
    tools: [],
    expanded: false
  },
  {
    id: 'blog_site',
    name: 'Blog Site Deploy',
    description: 'Scaffold a blog site, create a GitHub repo, deploy, and enable GitHub Pages',
    icon: Globe,
    tools: [],
    expanded: false
  },
  {
    id: 'contract',
    name: 'Contract Analysis',
    description: 'Analyze contracts and generate detailed contract reports',
    icon: FileText,
    tools: [],
    expanded: false
  },
  {
    id: 'browser',
    name: 'Browser Automation Tools',
    description: 'Web automation, screenshots, scraping, and browser interactions',
    icon: Globe,
    tools: [],
    expanded: false
  },
  {
    id: 'charts',
    name: 'Chart Tools',
    description: 'Generate charts and visualize query results',
    icon: Database,
    tools: [],
    expanded: false
  },
  {
    id: 'clickup',
    name: 'ClickUp Tools',
    description: 'Task management, comments, time tracking, and project organization',
    icon: Calendar,
    tools: [],
    expanded: false
  },
  {
    id: 'storage',
    name: 'Cloud Storage Tools',
    description: 'Upload, download, and manage cloud storage files',
    icon: Cloud,
    tools: [],
    expanded: false
  },
  {
    id: 'productivity',
    name: 'Cron & Scheduler Tools',
    description: 'Schedule recurring tasks, cron jobs, and automated workflows',
    icon: Calendar,
    tools: [],
    expanded: false
  },
  {
    id: 'csv_json',
    name: 'CSV & JSON Tools',
    description: 'Generate charts and analyze data from CSV and JSON files',
    icon: FileText,
    tools: [],
    expanded: false
  },
  {
    id: 'database',
    name: 'Database Tools',
    description: 'Query databases, generate charts, and manage connections',
    icon: Database,
    tools: [],
    expanded: false
  },
  {
    id: 'diagram',
    name: 'Diagram Tools',
    description: 'Generate architecture diagrams, flowcharts, sequence diagrams, ER diagrams, and more',
    icon: Package,
    tools: [],
    expanded: false
  },
  {
    id: 'infographic',
    name: 'Infographic Tools',
    description: 'Generate rich infographics, visual reports, and Slack-ready infographic images',
    icon: Package,
    tools: [],
    expanded: false
  },
  {
    id: 'image_generation',
    name: 'Image Generation',
    description: 'Generate AI images from text prompts using gpt-image-2, Google Imagen, or Grok Aurora — uses the agent\'s configured LLM API key',
    icon: Package,
    tools: [],
    expanded: false
  },
  {
    id: 'docker',
    name: 'Docker',
    description: 'Query Docker container logs and monitor running services',
    icon: Terminal,
    tools: [],
    expanded: false
  },
  {
    id: 'databricks',
    name: 'Databricks',
    description: 'Query and analyze data using Databricks',
    icon: Database,
    tools: [],
    expanded: false
  },
  {
    id: 'datadog',
    name: 'Datadog',
    description: 'Query Datadog metrics (time-series) and search log events for monitoring and debugging',
    icon: Database,
    tools: [],
    expanded: false
  },
  {
    id: 'documents',
    name: 'Document Generation',
    description: 'Generate PDFs, PowerPoint, Google Docs, and Google Sheets',
    icon: FileText,
    tools: [],
    expanded: false
  },
  {
    id: 'elasticsearch',
    name: 'Elasticsearch',
    description: 'Search, list indices, and get index stats from Elasticsearch',
    icon: Database,
    tools: [],
    expanded: false
  },
  {
    id: 'email',
    name: 'Email',
    description: 'Send emails, bulk emails, and test email connections via SMTP/SendGrid',
    icon: Mail,
    tools: [],
    expanded: false
  },
  {
    id: 'file_system',
    name: 'File System Tools',
    description: 'Read, write, search, and manage files and directories',
    icon: FileText,
    tools: [],
    expanded: false
  },
  {
    id: 'followup',
    name: 'Followup',
    description: 'Create, track, send, and manage follow-up items and messages',
    icon: MessageSquare,
    tools: [],
    expanded: false
  },
  {
    id: 'git_local',
    name: 'Git (Local)',
    description: 'Clone repos, manage branches, commit and push changes to any git host',
    icon: Github,
    tools: [],
    expanded: false
  },
  {
    id: 'github',
    name: 'GitHub',
    description: 'Manage issues, pull requests, code review, and repository info via GitHub API',
    icon: Github,
    tools: [],
    expanded: false
  },
  {
    id: 'gitlab',
    name: 'GitLab Tools',
    description: 'Projects, merge requests, issues, and repository management',
    icon: Github,
    tools: [],
    expanded: false
  },
  {
    id: 'gmail',
    name: 'Gmail Tools',
    description: 'Send, read, search, and manage emails',
    icon: MessageSquare,
    tools: [],
    expanded: false
  },
  {
    id: 'google_calendar',
    name: 'Google Calendar Tools',
    description: 'Manage calendar events and schedules',
    icon: Calendar,
    tools: [],
    expanded: false
  },
  {
    id: 'google_docs',
    name: 'Google Docs Tools',
    description: 'Create, read, and append content to Google Docs documents',
    icon: FileText,
    tools: [],
    expanded: false
  },
  {
    id: 'google_drive',
    name: 'Google Drive Tools',
    description: 'File storage, sharing, and collaboration',
    icon: Cloud,
    tools: [],
    expanded: false
  },
  {
    id: 'google_sheets',
    name: 'Google Sheets Tools',
    description: 'Create spreadsheets, read and write cell ranges',
    icon: Database,
    tools: [],
    expanded: false
  },
  {
    id: 'hackernews',
    name: 'Hacker News',
    description: 'Browse top, new, and best stories, search, and get trending topics',
    icon: Globe,
    tools: [],
    expanded: false
  },
  {
    id: 'jira',
    name: 'Jira Tools',
    description: 'Issue management, workflows, comments, and transitions',
    icon: Database,
    tools: [],
    expanded: false
  },
  {
    id: 'linkedin',
    name: 'LinkedIn Tools',
    description: 'Post updates, share content, and manage LinkedIn profile',
    icon: MessageSquare,
    tools: [],
    expanded: false
  },
  {
    id: 'news',
    name: 'News & RSS',
    description: 'Fetch news articles from NewsAPI or RSS/Atom feeds without getting blocked',
    icon: Newspaper,
    tools: [],
    expanded: false
  },
  {
    id: 'micromobility',
    name: 'Micromobility',
    description: 'Manage fleet vehicles, trips, riders, tasks, pricing, invoices, and analytics via Dashboard',
    icon: Globe,
    tools: [],
    expanded: false
  },
  {
    id: 'micromobility_intelligence',
    name: 'Micromobility Intelligence',
    description: 'AI-powered fleet analytics: health scoring, demand prediction, rebalancing plans, and batch task creation',
    icon: Database,
    tools: [],
    expanded: false
  },
  {
    id: 'openweather',
    name: 'Weather',
    description: 'Get current weather conditions and hourly forecasts for any location with demand impact scoring',
    icon: Globe,
    tools: [],
    expanded: false
  },
  {
    id: 'events_predicthq',
    name: 'Events (PredictHQ)',
    description: 'Discover nearby events from PredictHQ with attendance-based demand multipliers',
    icon: Calendar,
    tools: [],
    expanded: false
  },
  {
    id: 'events_ticketmaster',
    name: 'Events (Ticketmaster)',
    description: 'Discover nearby concerts, sports and live events from Ticketmaster with demand multipliers',
    icon: Calendar,
    tools: [],
    expanded: false
  },
  {
    id: 'mapbox',
    name: 'Mapbox',
    description: 'Generate static map images with vehicle markers and route overlays, plus turn-by-turn directions',
    icon: Globe,
    tools: [],
    expanded: false
  },
  {
    id: 'recall',
    name: 'Recall.ai Tools',
    description: 'Send bots to record meetings on Zoom, Meet, Teams, Slack Huddles',
    icon: Calendar,
    tools: [],
    expanded: false
  },
  {
    id: 'project',
    name: 'Project Tools',
    description: 'Get project info, read and update shared project context across agents',
    icon: Database,
    tools: [],
    expanded: false
  },
  {
    id: 'slack',
    name: 'Slack Tools',
    description: 'Send messages, search conversations, and manage channels',
    icon: MessageSquare,
    tools: [],
    expanded: false
  },
  {
    id: 'system',
    name: 'System & Command Tools',
    description: 'Execute system commands and manage processes',
    icon: Terminal,
    tools: [],
    expanded: false
  },
  {
    id: 'tutorial',
    name: 'Tutorial Generator',
    description: 'Fetch repo files, identify abstractions, analyze relationships, order chapters, and generate tutorials',
    icon: FileText,
    tools: [],
    expanded: false
  },
  {
    id: 'twitter',
    name: 'Twitter/X Tools',
    description: 'Post tweets, search, get timelines, and manage Twitter/X account',
    icon: MessageSquare,
    tools: [],
    expanded: false
  },
  {
    id: 'web_search',
    name: 'Web Search',
    description: 'Search the web and fetch content from URLs',
    icon: Search,
    tools: [],
    expanded: false
  },
  {
    id: 'youtube',
    name: 'YouTube',
    description: 'Get video transcripts, transcript segments, and available languages',
    icon: Globe,
    tools: [],
    expanded: false
  },
  {
    id: 'zoom',
    name: 'Zoom Tools',
    description: 'Video conferencing, meeting management, and recordings',
    icon: Calendar,
    tools: [],
    expanded: false
  },
  {
    id: 'custom',
    name: 'Custom Tools',
    description: 'Your custom API integrations and tools',
    icon: Package,
    tools: [],
    expanded: false
  }
];

// Tools are loaded dynamically from backend - no hardcoded placeholder tools
const NEW_TOOLS: Tool[] = [];

export default function AgentToolsPage() {
  const params = useParams();
  const router = useRouter();
  const agentName = params.agentName as string;

  const [agent, setAgent] = useState<any>(null);
  const [agentId, setAgentId] = useState<string | null>(null);
  const [agentTools, setAgentTools] = useState<AgentTool[]>([]);
  const [availableTools, setAvailableTools] = useState<Tool[]>([]);
  const [toolGroups, setToolGroups] = useState<ToolGroup[]>(TOOL_GROUPS);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeOnly, setActiveOnly] = useState(false);
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null);
  const [toolConfig, setToolConfig] = useState<Record<string, string>>({});
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [oauthApps, setOAuthApps] = useState<any[]>([]);
  const [allOAuthApps, setAllOAuthApps] = useState<any[]>([]);
  const [oauthStatus, setOAuthStatus] = useState<any>(null);
  const [customTools, setCustomTools] = useState<CustomTool[]>([]);
  const [userConnections, setUserConnections] = useState<Record<number, { connected: boolean; email?: string; username?: string; auth_method?: string }>>({});
  const [apiTokenModal, setApiTokenModal] = useState<{ open: boolean; appId: number | null; provider: string }>({ open: false, appId: null, provider: '' });
  const [apiTokenInput, setApiTokenInput] = useState('');
  const [savingApiToken, setSavingApiToken] = useState(false);
  const [slackBots, setSlackBots] = useState<any[]>([]);

  useEffect(() => {
    loadAgent();
    loadOAuthApps();
    loadAllOAuthApps();
    loadCustomTools();
    loadAvailableTools();
  }, [agentName]);

  useEffect(() => {
    // Load user connections once OAuth apps are loaded
    if (allOAuthApps.length > 0) {
      loadUserConnections();
    }
  }, [allOAuthApps]);

  useEffect(() => {
    if (selectedTool?.name === 'github' && agent?.id) {
      checkOAuthStatus();
    }
  }, [selectedTool, agent]);

  const loadAgent = async () => {
    try {
      const data = await apiClient.getAgent(agentName);
      setAgent(data);
      setAgentId(data.id);
      // Load tools and Slack bots immediately using the just-fetched ID
      await Promise.all([
        loadAgentTools(true, data.id),
        loadSlackBots(data.id),
      ]);
    } catch (error) {
      console.error('Failed to load agent:', error);
    }
  };

  const loadSlackBots = async (id?: string) => {
    const resolvedId = id ?? agentId;
    if (!resolvedId) return;
    try {
      const bots = await apiClient.getSlackBots(resolvedId);
      setSlackBots(Array.isArray(bots) ? bots : []);
    } catch (error) {
      console.error('Failed to load Slack bots:', error);
      setSlackBots([]);
    }
  };

  const loadAgentTools = async (showLoading = true, id?: string) => {
    const resolvedId = id ?? agentId;
    if (!resolvedId) return;
    try {
      if (showLoading) setLoading(true);
      const tools = await apiClient.getAgentToolsForAgent(resolvedId);
      setAgentTools(Array.isArray(tools) ? tools : []);
    } catch (error) {
      console.error('Failed to load agent tools:', error);
      setAgentTools([]);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  const loadOAuthApps = async () => {
    try {
      const data = await apiClient.getOAuthApps('github');
      setOAuthApps(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Failed to load OAuth apps:', error);
    }
  };

  const loadAllOAuthApps = async () => {
    try {
      const providers = ['github', 'gitlab', 'SLACK', 'gmail', 'zoom', 'google_calendar', 'google_drive', 'clickup', 'jira', 'twitter', 'linkedin', 'recall', 'newsapi', 'micromobility', 'openweather', 'predicthq', 'ticketmaster', 'mapbox'];
      const allApps: any[] = [];
      
      for (const provider of providers) {
        try {
          const data = await apiClient.getOAuthApps(provider);
          if (Array.isArray(data)) {
            allApps.push(...data);
          }
        } catch (error) {
          console.error(`Failed to load ${provider} OAuth apps:`, error);
        }
      }
      
      setAllOAuthApps(allApps);
    } catch (error) {
      console.error('Failed to load all OAuth apps:', error);
    }
  };

  const getOAuthAppsForProvider = (provider: string) => {
    // Case-insensitive provider matching
    const normalizedProvider = provider.toLowerCase();
    return allOAuthApps.filter(app =>
      app.provider?.toLowerCase() === normalizedProvider
    );
  };

  const loadUserConnections = async () => {
    try {
      const connections: Record<number, { connected: boolean; email?: string; username?: string; auth_method?: string }> = {};

      await Promise.all(
        allOAuthApps.map(async (app) => {
          try {
            const status = await apiClient.getUserConnectionStatus(app.id);
            connections[app.id] = {
              connected: status.connected,
              email: status.user_token?.provider_email,
              username: status.user_token?.provider_username,
              auth_method: status.auth_method
            };
          } catch (err) {
            connections[app.id] = { connected: false };
          }
        })
      );

      setUserConnections(connections);
    } catch (err) {
      console.error('Failed to load user connections:', err);
    }
  };

  const isUserConnectedToProvider = (provider: string) => {
    const providerApps = getOAuthAppsForProvider(provider);
    return providerApps.some(app => userConnections[app.id]?.connected);
  };

  const getAuthMethodForProvider = (provider: string) => {
    // Providers that only support API tokens (no OAuth flow)
    const apiTokenOnlyProviders = ['recall', 'TELEGRAM', 'onepassword', 'newsapi', 'micromobility', 'openweather', 'predicthq', 'ticketmaster', 'mapbox'];
    if (apiTokenOnlyProviders.includes(provider.toLowerCase()) ||
        apiTokenOnlyProviders.includes(provider)) {
      return 'api_token';
    }

    const providerApps = getOAuthAppsForProvider(provider);
    if (providerApps.length > 0) {
      return userConnections[providerApps[0].id]?.auth_method || providerApps[0].auth_method || 'oauth';
    }
    return 'oauth';
  };

  const getUserConnectionForProvider = (provider: string) => {
    const providerApps = getOAuthAppsForProvider(provider);
    const connectedApp = providerApps.find(app => userConnections[app.id]?.connected);
    if (connectedApp) {
      return userConnections[connectedApp.id];
    }
    return null;
  };

  const handleConnectProvider = async (provider: string) => {
    const providerApps = getOAuthAppsForProvider(provider);
    if (providerApps.length > 0) {
      const app = providerApps[0]; // Use first available app

      // Providers that only support API tokens (no OAuth flow)
      const apiTokenOnlyProviders = ['recall', 'TELEGRAM', 'onepassword', 'newsapi', 'micromobility', 'openweather', 'predicthq', 'ticketmaster', 'mapbox'];
      const isApiTokenOnly = apiTokenOnlyProviders.includes(provider.toLowerCase()) ||
                             apiTokenOnlyProviders.includes(provider);

      const authMethod = isApiTokenOnly ? 'api_token' :
                         (userConnections[app.id]?.auth_method || app.auth_method || 'oauth');

      if (authMethod === 'api_token') {
        // For API token apps, show modal to enter token
        setApiTokenModal({ open: true, appId: app.id, provider: app.provider });
        setApiTokenInput('');
      } else {
        // For OAuth apps, use secure AJAX-based initiation
        try {
          const result = await apiClient.initiateOAuth(app.id, window.location.href, true);
          window.location.href = result.auth_url;
        } catch (err) {
          toast.error(err instanceof Error ? err.message : 'Failed to initiate OAuth');
        }
      }
    }
  };

  const handleSaveApiToken = async () => {
    if (!apiTokenModal.appId || !apiTokenInput.trim()) {
      toast.error('Please enter an API token');
      return;
    }

    setSavingApiToken(true);
    try {
      await apiClient.saveUserApiToken(apiTokenModal.appId, apiTokenInput.trim());
      toast.success('API token saved successfully');
      setApiTokenModal({ open: false, appId: null, provider: '' });
      setApiTokenInput('');
      // Reload connections to reflect the change
      loadUserConnections();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save API token');
    } finally {
      setSavingApiToken(false);
    }
  };

  const loadCustomTools = async () => {
    try {
      const data = await apiClient.getCustomTools();
      setCustomTools(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Failed to load custom tools:', error);
      setCustomTools([]);
    }
  };

  const categorizeTools = (tools: Tool[]): ToolGroup[] => {
    const groups = [...TOOL_GROUPS];
    
    tools.forEach(tool => {
      const toolName = tool.name.toLowerCase();
      
      let groupId = 'system'; // default

      const AGENT_TOOLS = new Set(['spawn_agent', 'check_task', 'list_background_tasks', 'call_remote_agent', 'transfer_to_agent', 'escalate_to_human', 'get_my_human_contact', 'get_project_agents', 'get_my_role', 'internal_escalate_followup', 'check_escalation_status', 'get_pending_escalations', 'internal_search_available_tools', 'internal_list_tool_categories']);

      // Priority-based categorization by integration name
      if (AGENT_TOOLS.has(toolName)) {
        groupId = 'agents';
      } else if (toolName === 'get_project_info' || toolName === 'get_project_context' || toolName === 'update_project_context') {
        groupId = 'project';
      } else if (toolName.startsWith('internal_git_')) {
        groupId = 'git_local';
      } else if (toolName === 'internal_generate_blog_site' || toolName === 'internal_create_github_repository' || toolName === 'internal_deploy_blog_to_github' || toolName === 'internal_enable_github_pages') {
        groupId = 'blog_site';
      } else if (toolName.includes('github') || toolName.includes('pr_review')) {
        groupId = 'github';
      } else if (toolName.includes('gitlab')) {
        groupId = 'gitlab';
      } else if (toolName.includes('clickup')) {
        groupId = 'clickup';
      } else if (toolName.includes('jira') || toolName.includes('sprint')) {
        groupId = 'jira';
      } else if (toolName.includes('slack')) {
        groupId = 'slack';
      } else if (toolName.includes('zoom') || toolName.startsWith('internal_zoom_')) {
        groupId = 'zoom';
      } else if (toolName.startsWith('internal_google_calendar_')) {
        groupId = 'google_calendar';
      } else if (toolName.startsWith('internal_google_drive_')) {
        groupId = 'google_drive';
      } else if (toolName.includes('gmail')) {
        groupId = 'gmail';
      } else if (toolName.includes('twitter')) {
        groupId = 'twitter';
      } else if (toolName.includes('linkedin')) {
        groupId = 'linkedin';
      } else if (toolName.includes('recall')) {
        groupId = 'recall';
      } else if (toolName.includes('micromobility_get_fleet_health') ||
                 toolName.includes('micromobility_get_zone_demand') ||
                 toolName.includes('micromobility_predict_demand') ||
                 toolName.includes('micromobility_get_rebalancing') ||
                 toolName.includes('micromobility_batch_create') ||
                 toolName.includes('micromobility_get_trip_performance')) {
        groupId = 'micromobility_intelligence';
      } else if (toolName.includes('micromobility')) {
        groupId = 'micromobility';
      } else if (toolName.includes('get_weather_forecast') || toolName.includes('get_current_weather') || toolName.includes('openmeteo')) {
        groupId = 'openweather';
      } else if (toolName.includes('predicthq')) {
        groupId = 'events_predicthq';
      } else if (toolName.includes('ticketmaster')) {
        groupId = 'events_ticketmaster';
      } else if (toolName.includes('static_map') || toolName.includes('get_directions') || toolName.includes('mapbox')) {
        groupId = 'mapbox';
      }
      // Document generation tools - NEW!
      else if (toolName.includes('generate_pdf') || toolName.includes('generate_powerpoint') || 
               toolName.includes('generate_google_doc') || toolName.includes('generate_google_sheet') ||
               toolName.includes('_pdf') || toolName.includes('_pptx') || toolName.includes('_docx')) {
        groupId = 'documents';
      }
      // Browser automation tools - NEW!
      else if (toolName.includes('browser') || toolName.includes('navigate') || toolName.includes('screenshot') || 
               toolName.includes('extract_links') || toolName.includes('extract_structured_data') || 
               toolName.includes('check_element') || toolName.startsWith('internal_browser_')) {
        groupId = 'browser';
      }
      // Storage tools
      else if (toolName.includes('s3') || toolName.includes('storage')) {
        groupId = 'storage';
      }
      // Contract analysis tools
      else if (toolName === 'internal_analyze_contract' || toolName === 'internal_generate_contract_report') {
        groupId = 'contract';
      }
      // Tutorial generator tools — must come before file_system (fetch_repository_files contains 'file')
      else if (['internal_fetch_repository_files', 'internal_identify_abstractions', 'internal_analyze_relationships', 'internal_order_chapters', 'internal_generate_tutorial_chapter', 'internal_combine_tutorial'].includes(toolName)) {
        groupId = 'tutorial';
      }
      // Google Sheets tools — must come before file_system (read_range/write_range contain 'read'/'write')
      else if (toolName.startsWith('internal_google_sheets_')) {
        groupId = 'google_sheets';
      }
      // 1Password tools — must come before file_system (read_secret contains 'read')
      else if (toolName.startsWith('internal_1password_')) {
        groupId = 'onepassword';
      }
      // YouTube tools
      else if (toolName.startsWith('internal_youtube_') || toolName.startsWith('youtube_')) {
        groupId = 'youtube';
      }
      // Web search tools
      else if (toolName === 'web_search' || toolName === 'internal_web_fetch' || toolName === 'web_crawl') {
        groupId = 'web_search';
      }
      // Followup tools — must come before file_system (send_followup_message could match 'file' fragments)
      else if (toolName.includes('followup')) {
        groupId = 'followup';
      }
      // File system tools (but NOT storage)
      else if ((toolName.includes('read') || toolName.includes('write') || toolName.includes('file') ||
          toolName.includes('directory') || toolName.includes('search_files') || toolName.includes('edit')) &&
          !toolName.includes('s3') && !toolName.includes('storage')) {
        groupId = 'file_system';
      } else if (toolName === 'internal_generate_diagram' || toolName === 'internal_generate_quick_diagram') {
        groupId = 'diagram';
      } else if (toolName === 'internal_generate_infographic' || toolName === 'internal_generate_slack_infographic') {
        groupId = 'infographic';
      } else if (toolName === 'internal_generate_image') {
        groupId = 'image_generation';
      } else if (toolName === 'internal_generate_chart' || toolName === 'internal_query_and_chart') {
        groupId = 'charts';
      } else if (toolName === 'generate_chart_from_data') {
        groupId = 'csv_json';
      } else if (toolName === 'query_docker_logs') {
        groupId = 'docker';
      } else if (toolName === 'query_databricks') {
        groupId = 'databricks';
      } else if (toolName === 'query_datadog_metrics' || toolName === 'query_datadog_logs') {
        groupId = 'datadog';
      } else if (toolName === 'list_data_sources') {
        groupId = 'database';
      } else if (toolName === 'analyze_data_statistics' || toolName === 'export_data_report') {
        groupId = 'csv_json';
      } else if (toolName.includes('database') || toolName.includes('query') || toolName.includes('chart')) {
        groupId = 'database';
      } else if (toolName.startsWith('internal_google_docs_')) {
        groupId = 'google_docs';
      } else if (toolName.startsWith('internal_elasticsearch_')) {
        groupId = 'elasticsearch';
      } else if (toolName.startsWith('internal_hackernews_')) {
        groupId = 'hackernews';
      } else if (toolName === 'internal_news_search' || toolName === 'internal_fetch_rss_feed') {
        groupId = 'news';
      } else if (toolName.includes('command') || toolName.includes('execute')) {
        groupId = 'system';
      } else if (toolName === 'internal_send_email' || toolName === 'internal_send_bulk_emails' || toolName === 'internal_test_email_connection') {
        groupId = 'email';
      } else if (toolName.includes('calendar') || toolName.includes('schedule')) {
        groupId = 'productivity';
      }
      
      const group = groups.find(g => g.id === groupId);
      if (group && !group.tools.find(t => t.name === tool.name)) {
        group.tools.push(tool);
      }
    });
    
    return groups.filter(g => g.tools.length > 0 || g.id === 'custom');
  };

  const loadAvailableTools = async () => {
    try {
      const tools = await apiClient.getAgentTools();
      
      const transformedTools: Tool[] = tools.map((tool: any) => {
        const baseTool: any = {
          name: tool.name,
          displayName: tool.name.replace(/internal_/g, '').replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()),
          description: tool.description || 'No description available',
          category: 'web',
          icon: getToolIcon(tool.name),
          requiredFields: [] as ToolField[],
          optionalFields: [] as ToolField[],
          configurable: false
        };
        
        // Add OAuth selector for ALL internal_git_* tools (GitHub/Git tools)
        if (tool.name.startsWith('internal_git_')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'github';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'GitHub OAuth App',
              description: 'Select a configured GitHub OAuth app for authentication',
              placeholder: 'Select OAuth app',
              type: 'select',
              options: []
            }
          ];
        }
        
        // Add OAuth selector for ALL internal_github_* and internal_git_* tools
        if (tool.name.startsWith('internal_github_') ||
            tool.name.startsWith('internal_git_') ||
            tool.name === 'internal_create_github_repository' ||
            tool.name === 'internal_deploy_blog_to_github' ||
            tool.name === 'internal_enable_github_pages' ||
            tool.name.includes('pr_review')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'github';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'GitHub OAuth App',
              description: 'Select a configured GitHub OAuth app for authentication',
              placeholder: 'Select OAuth app',
              type: 'select',
              options: []
            }
          ];
        }
        
        // Add OAuth selector for ALL GitLab tools
        if (tool.name.includes('gitlab') && tool.name.startsWith('internal_')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'gitlab';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'GitLab Integration',
              description: 'Select a configured GitLab OAuth app or API token',
              placeholder: 'Select integration',
              type: 'select',
              options: []
            }
          ];
        }

        // Add OAuth selector for ALL internal_zoom_* tools (Zoom tools)
        if (tool.name.startsWith('internal_zoom_')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'zoom';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'Zoom OAuth App',
              description: 'Select a configured Zoom OAuth app for authentication',
              placeholder: 'Select OAuth app',
              type: 'select',
              options: []
            }
          ];
        }
        
        // Add OAuth selector for ALL internal_google_calendar_* tools
        if (tool.name.startsWith('internal_google_calendar_')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'google_calendar';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'Google Calendar OAuth App',
              description: 'Select a configured Google Calendar OAuth app for authentication',
              placeholder: 'Select OAuth app',
              type: 'select',
              options: []
            }
          ];
        }
        
        // Add OAuth selector for ALL internal_google_drive_* tools
        if (tool.name.startsWith('internal_google_drive_')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'google_drive';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'Google Drive OAuth App',
              description: 'Select a configured Google Drive OAuth app for authentication',
              placeholder: 'Select OAuth app',
              type: 'select',
              options: []
            }
          ];
        }
        
        // Add OAuth selector for ALL Slack tools (internal_slack_*, internal_send_slack_*, internal_search_slack_*, etc.)
        if (tool.name.includes('slack') && tool.name.startsWith('internal_')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'SLACK';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'Slack OAuth App',
              description: 'Select a configured Slack OAuth app for authentication',
              placeholder: 'Select OAuth app',
              type: 'select',
              options: []
            }
          ];
        }
        
        // Add OAuth selector for ALL ClickUp tools
        if (tool.name.includes('clickup') && tool.name.startsWith('internal_')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'clickup';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'ClickUp Integration',
              description: 'Select a configured ClickUp API token',
              placeholder: 'Select OAuth app',
              type: 'select',
              options: []
            }
          ];
        }
        
        // Add OAuth selector for ALL Jira tools
        if (tool.name.includes('jira') && tool.name.startsWith('internal_')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'jira';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'Jira Integration',
              description: 'Select a configured Jira API token with email and base URL',
              placeholder: 'Select OAuth app',
              type: 'select',
              options: []
            }
          ];
        }

        // Add OAuth selector for ALL Micromobility tools (raw + intelligence)
        if (tool.name.includes('micromobility')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'micromobility';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'Micromobility Integration',
              description: 'Select a configured Dashboard integration (API token or username/password)',
              placeholder: 'Select integration',
              type: 'select',
              options: []
            }
          ];
        }

        // OpenWeather tools
        if (tool.name.includes('get_weather_forecast') || tool.name.includes('get_current_weather')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'openweather';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'OpenWeather API Key',
              description: 'Select a configured OpenWeather integration (API key)',
              placeholder: 'Select integration',
              type: 'select',
              options: []
            }
          ];
        }

        // PredictHQ events tools
        if (tool.name.includes('predicthq')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'predicthq';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'PredictHQ API Key',
              description: 'Select a configured PredictHQ integration',
              placeholder: 'Select integration',
              type: 'select',
              options: []
            }
          ];
        }

        // Ticketmaster events tools
        if (tool.name.includes('ticketmaster')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'ticketmaster';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'Ticketmaster API Key',
              description: 'Select a configured Ticketmaster integration',
              placeholder: 'Select integration',
              type: 'select',
              options: []
            }
          ];
        }

        // Mapbox tools
        if (tool.name.includes('static_map') || tool.name.includes('get_directions')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'mapbox';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'Mapbox Access Token',
              description: 'Select a configured Mapbox integration',
              placeholder: 'Select integration',
              type: 'select',
              options: []
            }
          ];
        }

        // Add OAuth selector for ALL Gmail tools (both internal_gmail_* and gmail_* legacy tools)
        if (tool.name.includes('gmail')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'gmail';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'Gmail OAuth App',
              description: 'Select a configured Gmail OAuth app for authentication',
              placeholder: 'Select OAuth app',
              type: 'select',
              options: []
            }
          ];
        }

        // Add OAuth selector for ALL Twitter tools
        if (tool.name.includes('twitter') && tool.name.startsWith('internal_')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'twitter';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'Twitter/X OAuth App',
              description: 'Select a configured Twitter/X OAuth app for authentication',
              placeholder: 'Select OAuth app',
              type: 'select',
              options: []
            }
          ];
        }

        // Add OAuth selector for ALL LinkedIn tools
        if (tool.name.includes('linkedin') && tool.name.startsWith('internal_')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'linkedin';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'LinkedIn OAuth App',
              description: 'Select a configured LinkedIn OAuth app for authentication',
              placeholder: 'Select OAuth app',
              type: 'select',
              options: []
            }
          ];
        }

        // Add OAuth selector for NewsAPI tool
        if (tool.name === 'internal_news_search') {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'newsapi';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'NewsAPI OAuth App',
              description: 'Select a configured NewsAPI app (API Token)',
              placeholder: 'Select OAuth app',
              type: 'select',
              options: []
            }
          ];
        }

        // RSS feed tool needs no credentials
        if (tool.name === 'internal_fetch_rss_feed') {
          baseTool.configurable = false;
        }

        // Followup tools don't need configuration - can be enabled directly
        if (tool.name.startsWith('internal_followup_')) {
          baseTool.configurable = false;
        }

        // Add OAuth selector for ALL Recall.ai tools
        if (tool.name.startsWith('internal_recall_')) {
          baseTool.configurable = true;
          baseTool.oauthProvider = 'recall';
          baseTool.requiredFields = [
            {
              key: 'oauth_app_id',
              label: 'Recall.ai Integration',
              description: 'Select a configured Recall.ai API key',
              placeholder: 'Select integration',
              type: 'select',
              options: []
            }
          ];
        }
        
        return baseTool;
      });
      
      // Add new tools
      const allTools = [...transformedTools, ...NEW_TOOLS];
      setAvailableTools(allTools);
      
      // Categorize tools into groups
      const categorized = categorizeTools(allTools);
      setToolGroups(categorized);
    } catch (error) {
      console.error('Failed to load available tools:', error);
      setAvailableTools([]);
    }
  };

  const getToolIcon = (toolName: string): string => {
    const name = toolName.toLowerCase();
    if (name.includes('micromobility')) return '🛴';
    if (name.includes('weather')) return '🌤️';
    if (name.includes('predicthq') || name.includes('ticketmaster')) return '🎟️';
    if (name.includes('static_map') || name.includes('directions') || name.includes('mapbox')) return '🗺️';
    if (name.includes('recall')) return '🎥';
    if (name.includes('gitlab')) return '🦊';
    if (name.includes('twitter')) return '🐦';
    if (name.includes('linkedin')) return '💼';
    if (name.includes('gmail')) return '✉️';
    if (name === 'internal_send_email' || name === 'internal_send_bulk_emails' || name === 'internal_test_email_connection') return '📧';
    if (name.startsWith('internal_google_sheets_')) return '📊';
    if (name.startsWith('internal_google_docs_')) return '📝';
    if (name.startsWith('internal_elasticsearch_')) return '🔎';
    if (name === 'internal_generate_chart' || name === 'internal_query_and_chart') return '📊';
    if (name === 'generate_chart_from_data') return '📁';
    if (name === 'query_docker_logs') return '🐳';
    if (name === 'query_databricks') return '🧱';
    if (name === 'query_datadog_metrics') return '📈';
    if (name === 'query_datadog_logs') return '📋';
    if (name.startsWith('internal_hackernews_')) return '🗞️';
    if (name === 'internal_news_search') return '📰';
    if (name === 'internal_fetch_rss_feed') return '📡';
    if (['spawn_agent', 'transfer_to_agent', 'check_task', 'list_background_tasks', 'escalate_to_human', 'get_my_human_contact', 'get_project_agents', 'get_my_role', 'internal_escalate_followup', 'check_escalation_status', 'get_pending_escalations', 'internal_search_available_tools', 'internal_list_tool_categories'].includes(name)) return '🤖';
    if (name === 'get_project_info' || name === 'get_project_context' || name === 'update_project_context') return '🗂️';
    if (['internal_fetch_repository_files', 'internal_identify_abstractions', 'internal_analyze_relationships', 'internal_order_chapters', 'internal_generate_tutorial_chapter', 'internal_combine_tutorial'].includes(name)) return '📖';
    if (name === 'internal_analyze_contract' || name === 'internal_generate_contract_report') return '📋';
    if (name.startsWith('internal_1password_')) return '🔐';
    if (name.startsWith('internal_youtube_') || name.startsWith('youtube_')) return '▶️';
    if (name === 'web_search' || name === 'internal_web_fetch' || name === 'web_crawl') return '🌐';
    if (name.includes('followup')) return '🔔';
    if (name.includes('browser') || name.includes('navigate') || name.includes('screenshot')) return '🌐';
    if (name.includes('extract_links') || name.includes('extract_structured')) return '🔗';
    if (name.includes('check_element')) return '🔍';
    if (name.includes('read') || name.includes('file')) return '📄';
    if (name.includes('write') || name.includes('edit')) return '✏️';
    if (name.includes('search')) return '🔍';
    if (name.includes('directory') || name.includes('list')) return '📁';
    if (name === 'internal_generate_blog_site' || name === 'internal_create_github_repository' || name === 'internal_deploy_blog_to_github' || name === 'internal_enable_github_pages') return '🚀';
    if (name.includes('git') || name.includes('github')) return '🐙';
    if (name.includes('command') || name.includes('execute')) return '⚙️';
    if (name.includes('database') || name.includes('query')) return '🗄️';
    if (name.includes('chart')) return '📊';
    if (name.includes('s3') || name.includes('storage')) return '☁️';
    if (name.includes('tutorial')) return '📚';
    return '🔧';
  };

  const toggleGroup = (groupId: string) => {
    setToolGroups(prev => prev.map(g => 
      g.id === groupId ? { ...g, expanded: !g.expanded } : g
    ));
  };

  const deleteCustomTool = async (toolId: string) => {
    if (!confirm('Are you sure you want to delete this custom tool?')) {
      return;
    }

    try {
      await apiClient.deleteCustomTool(toolId);
      await loadCustomTools();
      toast.success('Custom tool deleted successfully');
    } catch (error) {
      console.error('Failed to delete custom tool:', error);
      toast.error('Failed to delete custom tool');
    }
  };

  const openCustomToolOperations = async () => {
    toast.error('Custom tool operations configuration is not yet implemented');
  };

  const checkOAuthStatus = async () => {
    if (!agent?.id || !selectedTool) return;
    
    try {
      const data = await apiClient.request(
        'GET',
        `/api/v1/oauth/github/status?agent_id=${agent.id}&tool_name=${selectedTool.name}`
      );
      setOAuthStatus(data);
    } catch (error) {
      console.error('Failed to check OAuth status:', error);
    }
  };

  const handleOAuthConnect = () => {
    if (!agent?.id || !selectedTool) return;
    
    const redirectUrl = encodeURIComponent(window.location.href);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001';
    window.location.href = `${apiUrl}/api/v1/oauth/github/authorize?agent_id=${agent.id}&tool_name=${selectedTool.name}&redirect_url=${redirectUrl}`;
  };

  const handleOAuthDisconnect = async () => {
    if (!agent?.id || !selectedTool) return;
    
    try {
      const data = await apiClient.request(
        'POST',
        '/api/v1/oauth/github/disconnect',
        {
          agent_id: agent.id,
          tool_name: selectedTool.name
        }
      );

      if (data.success) {
        setOAuthStatus({ connected: false, user: null, user_name: null });
        await loadAgentTools(false); // Don't show loading spinner
        toast.success('GitHub OAuth disconnected successfully');
      } else {
        toast.error(data.message || 'Failed to disconnect OAuth');
      }
    } catch (error) {
      console.error('Failed to disconnect OAuth:', error);
      toast.error('Failed to disconnect OAuth');
    }
  };

  const isToolEnabled = (toolName: string) => {
    if (!Array.isArray(agentTools)) return false;
    return agentTools.some(t => t.tool_name === toolName && t.enabled);
  };

  const getToolConfig = (toolName: string) => {
    if (!Array.isArray(agentTools)) return {};
    const tool = agentTools.find(t => t.tool_name === toolName);
    return tool?.config || {};
  };

  const openConfigModal = async (tool: Tool) => {
    // Create a copy of the tool to avoid mutating the original
    const toolCopy = JSON.parse(JSON.stringify(tool));

    // For Slack tools: rebuild the field to show bots + OAuth apps in one combined dropdown
    const isSlackTool = tool.name.includes('slack') && tool.name.startsWith('internal_');
    if (isSlackTool) {
      const activeBots = slackBots.filter(b => b.is_active);
      const botsToShow = activeBots.length > 0 ? activeBots : slackBots;
      const botOptions = botsToShow.map(b => ({
        value: `bot:${b.id}`,
        label: `${b.bot_name}${b.slack_workspace_name ? ` (${b.slack_workspace_name})` : ''} — ${b.connection_status}`,
        group: 'Slack Bots',
      }));
      const oauthOptions = getOAuthAppsForProvider('SLACK').map((app: any) => ({
        value: `oauth:${app.id}`,
        label: `${app.app_name}${app.has_access_token || app.has_api_token ? ' (connected)' : ''}`,
        group: 'OAuth Apps',
      }));
      const allOptions = [...botOptions, ...oauthOptions];

      // Replace the requiredField with a combined slack_connection field
      toolCopy.requiredFields = [
        {
          key: 'slack_connection',
          label: 'Slack Connection',
          description: 'Select a Slack bot or OAuth app to use for this tool.',
          placeholder: 'Select connection...',
          type: 'select',
          options: allOptions,
          isSlackCombined: true,
          noAccountsAvailable: allOptions.length === 0,
          providerName: 'SLACK',
        },
      ];

      // Reconstruct the current selection from saved agentTool
      const savedTool = agentTools.find(t => t.tool_name === tool.name);
      const initialConfig = getToolConfig(tool.name);
      // Carry over any non-slack-connection keys from the saved config
      const { slack_connection: _sc, ...otherConfig } = initialConfig as any;
      let preselected = '';
      if ((savedTool as any)?.slack_bot_id) {
        preselected = `bot:${(savedTool as any).slack_bot_id}`;
      } else if ((savedTool as any)?.oauth_app_id) {
        preselected = `oauth:${(savedTool as any).oauth_app_id}`;
      }
      setSelectedTool(toolCopy);
      setToolConfig({ ...otherConfig, slack_connection: preselected });
      return;
    }

    // Populate OAuth app options if tool uses OAuth
    if (toolCopy.oauthProvider) {
      const providerApps = getOAuthAppsForProvider(toolCopy.oauthProvider);
      const oauthField = toolCopy.requiredFields.find((f: ToolField) => f.key === 'oauth_app_id') ||
                         toolCopy.optionalFields?.find((f: ToolField) => f.key === 'oauth_app_id');
      if (oauthField) {
        // Update label to be more user-friendly
        oauthField.label = 'Connected Account';
        oauthField.description = `Select a ${toolCopy.oauthProvider} account to use with this tool`;

        if (!oauthField.options) {
          oauthField.options = [];
        }
        oauthField.options = providerApps.map((app: any) => {
          const isConfigured = app.has_access_token || app.has_api_token;
          const suffix = app.auth_method === 'basic_auth'
            ? isConfigured ? ' (configured)' : ' (missing credentials)'
            : isConfigured ? ' (connected)' : ' (not connected)';
          return {
            value: app.id.toString(),
            label: `${app.app_name}${app.is_default ? ' · Default' : ''}${suffix}`,
            isAuthorized: isConfigured,
          };
        });

        // Auto-select configured app for basic_auth / api_token providers —
        // no per-user flow needed, admin credentials are shared automatically.
        oauthField.autoSelectedAppId = null;
        const autoSelectApp = providerApps.find((a: any) =>
          (a.auth_method === 'basic_auth' || a.auth_method === 'api_token') &&
          (a.has_api_token || a.has_access_token)
        );
        if (autoSelectApp) {
          oauthField.autoSelectedAppId = autoSelectApp.id.toString();
        }

        // Mark if no accounts available
        oauthField.noAccountsAvailable = providerApps.length === 0;
        oauthField.providerName = toolCopy.oauthProvider;
      }
    }

    // Populate integration config options if tool uses integration configs
    if (toolCopy.integrationConfigType) {
      try {
        const configs = await apiClient.getIntegrationConfigs(toolCopy.integrationConfigType.toLowerCase());
        const configField = toolCopy.requiredFields.find((f: ToolField) => f.key === 'integration_config_id') ||
                           toolCopy.optionalFields?.find((f: ToolField) => f.key === 'integration_config_id');
        if (configField) {
          if (!configField.options) {
            configField.options = [];
          }
          configField.options = configs.map((config: any) => ({
            value: config.id.toString(),
            label: `${config.provider} (${config.integration_type})${config.is_platform_config ? ' - Default' : ''}`
          }));

          if (configs.length === 0) {
            configField.options.push({
              value: '',
              label: `No ${toolCopy.integrationConfigType} integrations configured`
            });
          }
        }
      } catch (error) {
        console.error('Failed to load integration configs:', error);
      }
    }

    const savedConfig = getToolConfig(tool.name);

    // If no oauth_app_id saved yet, auto-populate from the auto-selected app
    const oauthField = toolCopy.requiredFields?.find((f: any) => f.key === 'oauth_app_id') ||
                       toolCopy.optionalFields?.find((f: any) => f.key === 'oauth_app_id');
    const autoId = (oauthField as any)?.autoSelectedAppId;
    const mergedConfig = (autoId && !savedConfig.oauth_app_id)
      ? { ...savedConfig, oauth_app_id: autoId }
      : savedConfig;

    setSelectedTool(toolCopy);
    setToolConfig(mergedConfig);
  };

  const closeConfigModal = () => {
    setSelectedTool(null);
    setToolConfig({});
    setShowKeys({});
  };

  const handleConfigChange = (key: string, value: string) => {
    setToolConfig(prev => ({ ...prev, [key]: value }));
  };

  const toggleShowKey = (key: string) => {
    setShowKeys(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const saveTool = async () => {
    if (!selectedTool || !agentId) return;

    setSaving(true);
    try {
      // Extract oauth_app_id, slack_bot_id, custom_tool_id from config
      const { oauth_app_id, slack_connection, custom_tool_id, operation_id, ...remainingConfig } = toolConfig as any;

      // Parse combined slack_connection value (e.g. "bot:uuid" or "oauth:123")
      let resolvedOauthAppId: number | undefined = oauth_app_id ? parseInt(oauth_app_id, 10) : undefined;
      let resolvedSlackBotId: string | undefined = undefined;
      if (slack_connection) {
        if (slack_connection.startsWith('bot:')) {
          resolvedSlackBotId = slack_connection.slice(4);
        } else if (slack_connection.startsWith('oauth:')) {
          resolvedOauthAppId = parseInt(slack_connection.slice(6), 10);
        }
      }

      await apiClient.addToolToAgent(agentId, {
        tool_name: selectedTool.name,
        config: remainingConfig,
        enabled: true,
        oauth_app_id: resolvedOauthAppId,
        slack_bot_id: resolvedSlackBotId,
        custom_tool_id: custom_tool_id || undefined,
        operation_id: operation_id || undefined
      });

      await loadAgentTools(false); // Don't show loading spinner
      closeConfigModal();
      toast.success('Tool configuration saved successfully');
    } catch (error: any) {
      console.error('Failed to save tool:', error);
      toast.error(`Failed to save tool configuration: ${error.message || 'Unknown error'}`);
    } finally {
      setSaving(false);
    }
  };

  const testTool = async () => {
    if (!selectedTool || !agentId) return;

    setTesting(true);
    try {
      const result = await apiClient.testAgentTool(agentId, selectedTool.name, { config: toolConfig });
      
      if (result.success) {
        toast.success('Tool configuration test successful!');
      } else {
        toast.error(`Test failed: ${result.error || result.message || 'Unknown error'}`);
      }
    } catch (error: any) {
      toast.error(`Test failed: ${error.message || 'Unknown error'}`);
    } finally {
      setTesting(false);
    }
  };

  const toggleTool = async (toolName: string, enabled: boolean) => {
    if (!agentId) return;
    try {
      if (enabled) {
        // Disabling tool - find and delete it
        const agentTool = agentTools.find(t => t.tool_name === toolName);

        if (agentTool) {
          try {
            await apiClient.deleteAgentTool(agentId, agentTool.id.toString());
            await loadAgentTools(false); // Don't show loading spinner
            toast.success('Tool disabled successfully');
          } catch (error: any) {
            console.error('Failed to disable tool:', error);
            toast.error(`Failed to disable tool: ${error.message || 'Unknown error'}`);
          }
        }
      } else {
        // Enabling tool
        const tool = availableTools.find((t: Tool) => t.name === toolName);
        if (tool) {
          // If tool is not configurable, enable it directly
          if (!tool.configurable) {
            setSaving(true);
            try {
              await apiClient.addToolToAgent(agentId, {
                tool_name: tool.name,
                config: {},
                enabled: true
              });

              await loadAgentTools(false); // Don't show loading spinner
              toast.success(`${tool.displayName} enabled successfully`);
            } catch (error: any) {
              console.error('Failed to enable tool:', error);
              toast.error(`Failed to enable tool: ${error.message || 'Unknown error'}`);
            } finally {
              setSaving(false);
            }
          } else {
            // If configurable, open the modal
            openConfigModal(tool);
          }
        }
      }
    } catch (error) {
      console.error('Failed to toggle tool:', error);
    }
  };

  // Handle capability toggle (enable/disable all tools in a capability)
  const handleCapabilityToggle = async (capabilityId: string, enabled: boolean) => {
    try {
      if (!agent?.id) {
        toast.error('Agent not loaded');
        return;
      }

      if (enabled) {
        // Enable all tools for this capability
        await apiClient.enableCapability(agent.id, capabilityId);
        toast.success('Capability enabled');
      } else {
        // Disable all tools for this capability
        await apiClient.disableCapability(agent.id, capabilityId);
        toast.success('Capability disabled');
      }

      // Reload tools to reflect changes (without showing loading spinner)
      await loadAgentTools(false);
    } catch (error) {
      console.error('Failed to toggle capability:', error);
      toast.error('Failed to toggle capability');
    }
  };

  // Get list of enabled tool names for capability component
  const enabledToolNames = agentTools.filter(t => t.enabled).map(t => t.tool_name);

  const filteredGroups = toolGroups.map(group => {
    if (group.id === 'custom') {
      const filtered = customTools.filter(tool =>
        (searchQuery === '' || tool.name.toLowerCase().includes(searchQuery.toLowerCase()) || tool.description?.toLowerCase().includes(searchQuery.toLowerCase())) &&
        (!activeOnly || tool.enabled)
      );
      return { ...group, filteredCustomTools: filtered };
    }

    const filtered = group.tools.filter(tool =>
      (searchQuery === '' || tool.displayName.toLowerCase().includes(searchQuery.toLowerCase()) || tool.description.toLowerCase().includes(searchQuery.toLowerCase())) &&
      (!activeOnly || enabledToolNames.includes(tool.name))
    );
    return { ...group, tools: filtered, filteredCustomTools: [] };
  }).filter(group =>
    group.id === 'custom'
      ? (group.filteredCustomTools.length > 0) || (searchQuery === '' && !activeOnly)
      : group.tools.length > 0
  );

  return (
    <AgentPageShell
      agentName={agentName}
      title="Tool Configuration"
      description={<>Configure tools for <span className="font-semibold text-gray-900">{agent?.agent_name || agentName}</span>.</>}
      icon={Settings}
      backHref={`/agents/${agentName}/view`}
      backLabel="Back to Agent"
      badge="Capability Control"
      maxWidthClassName="max-w-7xl"
    >
      <div className="px-0 py-0">
        {/* Search Bar + Active Filter */}
        <div className="mb-5 flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search tools..."
              className="w-full pl-10 pr-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 bg-white"
            />
          </div>
          <button
            onClick={() => setActiveOnly(v => !v)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium rounded-lg border transition-colors whitespace-nowrap ${
              activeOnly
                ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
            }`}
          >
            <CheckCircle className={`w-4 h-4 ${activeOnly ? 'text-emerald-600' : 'text-gray-400'}`} />
            Active only
            {activeOnly && (
              <span className="ml-1 bg-emerald-100 text-emerald-700 text-xs font-semibold px-1.5 py-0.5 rounded-full">
                {agentTools.filter(t => t.enabled).length}
              </span>
            )}
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow-sm p-3.5 border border-gray-200">
            <div className="text-xs text-gray-600">Total Tools</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">
              {availableTools.length + customTools.length}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-3.5 border border-gray-200">
            <div className="text-xs text-gray-600">Enabled Tools</div>
            <div className="text-2xl font-bold text-emerald-600 mt-1">
              {agentTools.filter(t => t.enabled).length}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-3.5 border border-gray-200">
            <div className="text-xs text-gray-600">Built-in Tools</div>
            <div className="text-2xl font-bold text-red-600 mt-1">
              {availableTools.length}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-3.5 border border-gray-200">
            <div className="text-xs text-gray-600">Custom Tools</div>
            <div className="text-2xl font-bold text-purple-600 mt-1">
              {customTools.length}
            </div>
          </div>
        </div>

        {/* Capability Toggles */}
        {agent?.id && (
          <CapabilityToggles
            agentId={agent.id}
            enabledToolNames={enabledToolNames}
            onCapabilityToggle={handleCapabilityToggle}
          />
        )}

        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600 mx-auto"></div>
            <p className="mt-4 text-sm text-gray-600">Loading tools...</p>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Tool Groups */}
            {filteredGroups.map((group: any) => {
              // Determine OAuth provider for this group
              const groupOAuthProvider = (() => {
                if (group.id === 'github') return 'github';
                if (group.id === 'gitlab') return 'gitlab';
                if (group.id === 'slack') return 'SLACK';
                if (group.id === 'zoom') return 'zoom';
                if (group.id === 'google_calendar') return 'google_calendar';
                if (group.id === 'google_drive') return 'google_drive';
                if (group.id === 'clickup') return 'clickup';
                if (group.id === 'jira') return 'jira';
                if (group.id === 'gmail') return 'gmail';
                if (group.id === 'twitter') return 'twitter';
                if (group.id === 'linkedin') return 'linkedin';
                if (group.id === 'recall') return 'recall';
                if (group.id === 'micromobility') return 'micromobility';
                if (group.id === 'micromobility_intelligence') return 'micromobility';
                if (group.id === 'openweather') return 'openweather';
                if (group.id === 'events_predicthq') return 'predicthq';
                if (group.id === 'events_ticketmaster') return 'ticketmaster';
                if (group.id === 'mapbox') return 'mapbox';
                return null;
              })();

              const hasOAuthApps = groupOAuthProvider ? getOAuthAppsForProvider(groupOAuthProvider).length > 0 : false;
              const isConnected = groupOAuthProvider ? isUserConnectedToProvider(groupOAuthProvider) : false;
              const userConnection = groupOAuthProvider ? getUserConnectionForProvider(groupOAuthProvider) : null;
              const authMethod = groupOAuthProvider ? getAuthMethodForProvider(groupOAuthProvider) : 'oauth';

              return (
              <div key={group.id} className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:border-red-200 transition-all">
                <button
                  onClick={() => toggleGroup(group.id)}
                  className="w-full flex items-center justify-between p-5 hover:bg-red-50/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-red-50 rounded-lg">
                      <group.icon className="w-5 h-5 text-red-600" />
                    </div>
                    <div className="text-left">
                      <h2 className="text-base font-semibold text-gray-900">{group.name}</h2>
                      <p className="text-xs text-gray-600">{group.description}</p>
                    </div>
                    <span className="ml-3 px-2.5 py-0.5 bg-gray-100 text-gray-700 rounded-full text-xs font-medium">
                      {group.id === 'custom'
                        ? customTools.length
                        : group.tools.length} tools
                    </span>
                    {/* User Connection Status */}
                    {groupOAuthProvider && hasOAuthApps && (
                      isConnected ? (
                        <span className="ml-2 inline-flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 text-emerald-700 rounded-full text-xs font-medium">
                          <CheckCircle className="w-3.5 h-3.5" />
                          {authMethod === 'api_token' ? 'Token configured' : (userConnection?.email || userConnection?.username || 'Connected')}
                        </span>
                      ) : (
                        <span
                          onClick={(e) => {
                            e.stopPropagation();
                            handleConnectProvider(groupOAuthProvider);
                          }}
                          className="ml-2 inline-flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 text-amber-700 rounded-full text-xs font-medium cursor-pointer hover:bg-amber-100 transition-colors"
                        >
                          <Link2 className="w-3.5 h-3.5" />
                          {authMethod === 'api_token' ? 'Add your token' : 'Connect your account'}
                        </span>
                      )
                    )}
                  </div>
                  {group.expanded ? (
                    <ChevronDown className="w-4 h-4 text-gray-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-400" />
                  )}
                </button>

                {group.expanded && (
                  <div className="border-t border-gray-200 p-5">
                    {group.id === 'custom' ? (
                      <>
                        {group.filteredCustomTools && group.filteredCustomTools.length > 0 ? (
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {group.filteredCustomTools.map((tool: CustomTool) => (
                              <div
                                key={tool.id}
                                className="bg-gray-50 rounded-lg p-3.5 border border-gray-200 hover:border-red-300 hover:shadow-md transition-all"
                              >
                                <div className="flex items-start justify-between mb-2.5">
                                  <div className="flex items-center gap-2.5">
                                    {tool.icon ? (
                                      <img src={tool.icon} alt="" className="w-7 h-7 rounded" />
                                    ) : (
                                      <div className="text-xl">🔧</div>
                                    )}
                                    <div>
                                      <h3 className="text-sm font-semibold text-gray-900">{tool.name}</h3>
                                      <span className="text-xs text-gray-500 uppercase">{tool.auth_type}</span>
                                    </div>
                                  </div>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      deleteCustomTool(tool.id);
                                    }}
                                    className="p-1 rounded text-red-600 hover:bg-red-50 transition-colors"
                                  >
                                    <X className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                                <p className="text-xs text-gray-600 mb-2.5 line-clamp-2">{tool.description || 'No description'}</p>
                                <div className="text-xs text-gray-500 truncate mb-2.5">{tool.server_url}</div>
                                <button
                                  onClick={() => openCustomToolOperations()}
                                  className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-xs"
                                >
                                  <Settings className="w-3.5 h-3.5" />
                                  Configure
                                </button>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-center py-8 text-gray-500">
                            {searchQuery ? 'No custom tools match your search' : 'No custom tools yet. Add your first custom tool above.'}
                          </div>
                        )}
                      </>
                    ) : group.tools.length > 0 ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {group.tools.map((tool: Tool) => {
                          const enabled = isToolEnabled(tool.name);
                          return (
                            <div
                              key={tool.name}
                              className="bg-gray-50 rounded-lg p-3.5 border border-gray-200 hover:border-red-300 hover:shadow-md transition-all"
                            >
                              <div className="flex items-start justify-between mb-2.5">
                                <div className="flex items-center gap-2.5">
                                  <div className="text-xl">{tool.icon}</div>
                                  <div>
                                    <h3 className="text-sm font-semibold text-gray-900">{tool.displayName}</h3>
                                    {enabled && (
                                      <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
                                        <Check className="w-3 h-3" />
                                        Enabled
                                      </span>
                                    )}
                                  </div>
                                </div>
                                <button
                                  onClick={() => toggleTool(tool.name, enabled)}
                                  className={`p-1.5 rounded-lg transition-colors ${
                                    enabled
                                      ? 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100'
                                      : 'bg-gray-200 text-gray-400 hover:bg-gray-300'
                                  }`}
                                >
                                  {enabled ? <Check className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
                                </button>
                              </div>
                              <p className="text-xs text-gray-600 mb-2.5 line-clamp-2">{tool.description}</p>
                              {enabled && tool.configurable && (
                                <button
                                  onClick={() => openConfigModal(tool)}
                                  className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors text-xs"
                                >
                                  <Settings className="w-3.5 h-3.5" />
                                  Configure
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="text-center py-8 text-gray-500">
                        No tools match your search
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
            })}
          </div>
        )}
      </div>

      {/* Configuration Modal */}
      {selectedTool && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#171717]/55 p-4 backdrop-blur-md">
          <div className={`${toolModalShellClass} flex max-h-[88vh] flex-col`}>
            <div className="sticky top-0 z-10 border-b border-black/8 bg-white/95 px-8 py-6 backdrop-blur">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-14 w-14 items-center justify-center rounded-[1.25rem] border border-black/8 bg-[#fff5f3] text-[1.7rem] shadow-sm">
                    <span>{selectedTool.icon}</span>
                  </div>
                  <div>
                    <h2 className="text-[2rem] font-semibold tracking-[-0.03em] text-[#171717]">
                      {selectedTool.displayName}
                    </h2>
                    <p className="max-w-3xl text-base leading-7 text-[#6d675f]">
                      {selectedTool.description}
                    </p>
                  </div>
                </div>
                <button
                  onClick={closeConfigModal}
                  className="flex h-11 w-11 items-center justify-center rounded-2xl border border-black/8 bg-[#fcfaf5] text-[#171717] transition hover:bg-[#f3ecdf]"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            <div className="flex-1 space-y-6 overflow-y-auto bg-[#f6f1e7] px-8 py-7">
              {/* Required Fields */}
              {selectedTool.requiredFields.length > 0 && (
                <section className={toolModalSectionClass}>
                  <div className="mb-5">
                    <h3 className="text-lg font-semibold tracking-[-0.02em] text-[#171717]">Required Configuration</h3>
                    <p className="mt-1 text-sm text-[#6d675f]">
                      Add the minimum setup this tool needs before it can be tested or saved.
                    </p>
                  </div>
                  <div className="space-y-5">
                    {selectedTool.requiredFields.map(field => (
                      <div key={field.key}>
                        <label className={toolModalLabelClass}>
                          {field.label}
                        </label>
                        <p className={toolModalHelpClass}>{field.description}</p>
                        {field.type === 'select' && field.key === 'slack_connection' ? (
                          // Combined Slack bot + OAuth app dropdown
                          (field as any).noAccountsAvailable ? (
                            <div className="rounded-[1.25rem] border border-amber-200 bg-amber-50/90 p-4">
                              <div className="flex items-start gap-3">
                                <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                                <div className="flex-1">
                                  <p className="text-sm font-medium text-amber-800">No Slack connections found</p>
                                  <p className="text-xs text-amber-700 mt-1">
                                    Connect a Slack bot to this agent or add a Slack OAuth app.
                                  </p>
                                  <div className="flex gap-2 mt-3">
                                    <Link
                                      href={`/agents/${agentName}/slack-bots/create`}
                                      className="inline-flex items-center gap-1.5 rounded-xl bg-amber-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-amber-700"
                                    >
                                      <Link2 className="w-3.5 h-3.5" />
                                      Add Slack Bot
                                    </Link>
                                    <Link
                                      href="/oauth-apps/create"
                                      className="inline-flex items-center gap-1.5 rounded-xl border border-amber-300 px-3 py-2 text-xs font-medium text-amber-700 transition-colors hover:bg-amber-100"
                                    >
                                      Add OAuth App
                                    </Link>
                                  </div>
                                </div>
                              </div>
                            </div>
                          ) : (
                            <div>
                              <select
                                value={toolConfig['slack_connection'] || ''}
                                onChange={(e) => handleConfigChange('slack_connection', e.target.value)}
                                className={toolModalFieldClass}
                              >
                                <option value="">Select connection (uses bot auto-detect if empty)</option>
                                {(() => {
                                  const groups: Record<string, any[]> = {};
                                  (field.options || []).forEach((opt: any) => {
                                    const g = opt.group || 'Other';
                                    if (!groups[g]) groups[g] = [];
                                    groups[g].push(opt);
                                  });
                                  return Object.entries(groups).map(([groupLabel, opts]) => (
                                    <optgroup key={groupLabel} label={groupLabel}>
                                      {opts.map((opt: any) => (
                                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                                      ))}
                                    </optgroup>
                                  ));
                                })()}
                              </select>
                              <p className="mt-2 text-xs text-[#6d675f]">
                                Leave empty to auto-detect the connected Slack bot.
                              </p>
                            </div>
                          )
                        ) : field.type === 'select' && field.key === 'oauth_app_id' ? (
                          // Special handling for non-Slack Connected Account dropdown
                          (field as any).noAccountsAvailable ? (
                            <div className="rounded-[1.25rem] border border-amber-200 bg-amber-50/90 p-4">
                              <div className="flex items-start gap-3">
                                <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                                <div className="flex-1">
                                  <p className="text-sm font-medium text-amber-800">
                                    No {(field as any).providerName} account connected
                                  </p>
                                  <p className="text-xs text-amber-700 mt-1">
                                    You need to connect a {(field as any).providerName} account before using this tool.
                                  </p>
                                  <Link
                                    href="/oauth-apps/create"
                                    className="mt-3 inline-flex items-center gap-1.5 rounded-xl bg-amber-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-amber-700"
                                  >
                                    <Link2 className="w-3.5 h-3.5" />
                                    Connect {(field as any).providerName} Account
                                  </Link>
                                </div>
                              </div>
                            </div>
                          ) : (
                            <div>
                              <select
                                value={toolConfig[field.key] != null ? String(toolConfig[field.key]) : ''}
                                onChange={(e) => handleConfigChange(field.key, e.target.value)}
                                className={toolModalFieldClass}
                              >
                                <option value="">Select an account</option>
                                {field.options?.map(opt => (
                                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                              </select>
                              <div className="mt-2 flex items-center justify-between">
                                <p className="text-xs text-[#6d675f]">
                                  Select an account or{' '}
                                  <Link href="/oauth-apps/create" className={toolModalLinkClass}>
                                    connect a new one
                                  </Link>
                                </p>
                              </div>
                            </div>
                          )
                        ) : field.type === 'select' && field.options ? (
                          <select
                            value={toolConfig[field.key] || ''}
                            onChange={(e) => handleConfigChange(field.key, e.target.value)}
                            className={toolModalFieldClass}
                          >
                            <option value="">Select {field.label}</option>
                            {field.options.map(opt => (
                              <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                          </select>
                        ) : field.type === 'textarea' ? (
                          <textarea
                            value={toolConfig[field.key] || ''}
                            onChange={(e) => handleConfigChange(field.key, e.target.value)}
                            placeholder={field.placeholder}
                            rows={4}
                            className={`${toolModalFieldClass} min-h-[112px] resize-y`}
                          />
                        ) : (
                          <div className="relative">
                            <input
                              type={showKeys[field.key] ? 'text' : field.type}
                              value={toolConfig[field.key] || ''}
                              onChange={(e) => handleConfigChange(field.key, e.target.value)}
                              placeholder={field.placeholder}
                              className={`${toolModalFieldClass} pr-11`}
                            />
                            {field.type === 'password' && (
                              <button
                                type="button"
                                onClick={() => toggleShowKey(field.key)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#8b857d] transition hover:text-[#171717]"
                              >
                                {showKeys[field.key] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Optional Fields */}
              {selectedTool.optionalFields && selectedTool.optionalFields.length > 0 && (
                <section className={toolModalSectionClass}>
                  <div className="mb-5">
                    <h3 className="text-lg font-semibold tracking-[-0.02em] text-[#171717]">Optional Configuration</h3>
                    <p className="mt-1 text-sm text-[#6d675f]">
                      Add extra values only if this tool needs custom behavior.
                    </p>
                  </div>
                  <div className="space-y-5">
                    {selectedTool.optionalFields.map(field => (
                      <div key={field.key}>
                        <label className={toolModalLabelClass}>
                          {field.label}
                        </label>
                        <p className={toolModalHelpClass}>{field.description}</p>
                        <div className="relative">
                          <input
                            type={showKeys[field.key] ? 'text' : field.type}
                            value={toolConfig[field.key] || ''}
                            onChange={(e) => handleConfigChange(field.key, e.target.value)}
                            placeholder={field.placeholder}
                            className={`${toolModalFieldClass} pr-11`}
                          />
                          {field.type === 'password' && (
                            <button
                              type="button"
                              onClick={() => toggleShowKey(field.key)}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-[#8b857d] transition hover:text-[#171717]"
                            >
                              {showKeys[field.key] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* GitHub Account Connection Section */}
              {selectedTool.name === 'github' && (
                <section className={toolModalSectionClass}>
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-semibold tracking-[-0.02em] text-[#171717]">GitHub Account</h3>
                      <p className="mt-1 text-sm text-[#6d675f]">
                        Connect your GitHub account for enhanced access and higher rate limits
                      </p>
                    </div>
                  </div>

                  {oauthApps.length === 0 ? (
                    <div className="rounded-[1.25rem] border border-amber-200 bg-amber-50/90 p-4">
                      <div className="flex items-start gap-3">
                        <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                        <div>
                          <p className="text-sm font-medium text-amber-800">
                            No GitHub account connected
                          </p>
                          <p className="text-xs text-amber-700 mt-1">
                            Connect your GitHub account to use this tool with full functionality.
                          </p>
                          <Link
                            href="/oauth-apps/create"
                            className="mt-3 inline-flex items-center gap-1.5 rounded-xl bg-amber-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-amber-700"
                          >
                            <Link2 className="w-3.5 h-3.5" />
                            Connect GitHub Account
                          </Link>
                        </div>
                      </div>
                    </div>
                  ) : oauthStatus?.connected ? (
                    <div className="rounded-[1.25rem] border border-emerald-200 bg-emerald-50/90 p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-100">
                            <Github className="w-5 h-5 text-emerald-700" />
                          </div>
                          <div>
                            <p className="text-sm font-medium text-emerald-900">
                              Connected as @{oauthStatus.user}
                            </p>
                            {oauthStatus.user_name && (
                              <p className="text-xs text-emerald-700">{oauthStatus.user_name}</p>
                            )}
                          </div>
                        </div>
                        <button
                          onClick={handleOAuthDisconnect}
                          className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-red-600 transition-colors hover:bg-red-50"
                        >
                          <Unlink className="w-4 h-4" />
                          Disconnect
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={handleOAuthConnect}
                      className="flex w-full items-center justify-center gap-3 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
                    >
                      <Github className="w-5 h-5" />
                      Connect with GitHub
                    </button>
                  )}
                </section>
              )}

            </div>

            <div className="sticky bottom-0 flex items-center justify-end gap-3 border-t border-black/8 bg-[#f5eedf]/95 px-8 py-4 backdrop-blur">
              <button
                onClick={closeConfigModal}
                className="rounded-2xl border border-black/10 bg-transparent px-4 py-2.5 text-sm font-medium text-[#5f5a54] transition hover:bg-white/70"
              >
                Cancel
              </button>
              {selectedTool.configurable && (
                <>
                  <button
                    onClick={testTool}
                    disabled={testing}
                    className="flex items-center gap-2 rounded-2xl border border-black/10 bg-white px-4 py-2.5 text-sm font-medium text-[#171717] transition hover:bg-[#fcfaf5] disabled:opacity-50"
                  >
                    <TestTube className="h-4 w-4" />
                    {testing ? 'Testing...' : 'Test'}
                  </button>
                  <button
                    onClick={saveTool}
                    disabled={saving}
                    className="flex items-center gap-2 rounded-2xl bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-black disabled:opacity-50"
                  >
                    <Save className="h-4 w-4" />
                    {saving ? 'Saving...' : 'Save'}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Custom Tool Modal & Operations Modal remain the same as original */}
      {/* Keeping existing modal implementations for custom tools and operations */}

      {/* API Token Modal */}
      {apiTokenModal.open && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full mx-4 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">
                Add Your {apiTokenModal.provider} API Token
              </h3>
              <button
                onClick={() => setApiTokenModal({ open: false, appId: null, provider: '' })}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="px-6 py-4">
              <p className="text-sm text-gray-600 mb-4">
                Enter your personal API token for {apiTokenModal.provider}. This token will be used for your account only.
              </p>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                API Token
              </label>
              <input
                type="password"
                value={apiTokenInput}
                onChange={(e) => setApiTokenInput(e.target.value)}
                placeholder="Enter your API token"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 text-sm"
              />
              <p className="mt-2 text-xs text-gray-500">
                Your token is encrypted and stored securely.
              </p>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setApiTokenModal({ open: false, appId: null, provider: '' })}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveApiToken}
                disabled={savingApiToken || !apiTokenInput.trim()}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {savingApiToken ? 'Saving...' : 'Save Token'}
              </button>
            </div>
          </div>
        </div>
      )}
    </AgentPageShell>
  );
}
