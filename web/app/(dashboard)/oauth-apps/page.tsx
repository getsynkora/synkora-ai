'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import { apiClient } from '@/lib/api/client'
import { CheckCircle, AlertCircle, ExternalLink, Plus, Settings, Trash2, Link2, Unlink, Shield, User, Copy, Check, Webhook } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

interface OAuthApp {
  id: number
  provider: string
  app_name: string
  auth_method: string
  client_id: string
  redirect_uri: string
  scopes: string[] | null
  is_active: boolean
  is_default: boolean
  is_platform_app?: boolean
  source?: 'tenant' | 'platform'
  description: string | null
  created_at: string
  updated_at: string
  has_access_token?: boolean
  has_refresh_token?: boolean
  has_api_token?: boolean
  has_private_key?: boolean
  token_expires_at?: string | null
}

interface UserConnection {
  app_id: number
  connected: boolean
  admin_connected?: boolean
  auth_method?: string
  user_token?: {
    id: string
    provider_email: string
    provider_username: string
    provider_display_name: string
    created_at: string
  }
}

const PROVIDER_CONFIG: Record<string, {
  name: string
  icon: React.ReactNode
  color: string
  bgColor: string
  borderColor: string
  description: string
  setupUrl: string
}> = {
  github: {
    name: 'GitHub',
    icon: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
        <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
      </svg>
    ),
    color: 'text-gray-900',
    bgColor: 'bg-gray-100',
    borderColor: 'border-gray-200',
    description: 'Repositories, issues, and pull requests',
    setupUrl: 'https://github.com/settings/developers',
  },
  gitlab: {
    name: 'GitLab',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none">
        <path fill="#E24329" d="M12 22.1L15.9 11H8.1L12 22.1Z"/>
        <path fill="#FC6D26" d="M12 22.1L8.1 11H1.3L12 22.1Z"/>
        <path fill="#FCA326" d="M1.3 11L0 14.9C-0.1 15.3 0.1 15.7 0.5 15.9L12 22.1L1.3 11Z"/>
        <path fill="#E24329" d="M1.3 11H8.1L5.2 1.9C5 1.4 4.3 1.4 4.1 1.9L1.3 11Z"/>
        <path fill="#FC6D26" d="M12 22.1L15.9 11H22.7L12 22.1Z"/>
        <path fill="#FCA326" d="M22.7 11L24 14.9C24.1 15.3 23.9 15.7 23.5 15.9L12 22.1L22.7 11Z"/>
        <path fill="#E24329" d="M22.7 11H15.9L18.8 1.9C19 1.4 19.7 1.4 19.9 1.9L22.7 11Z"/>
      </svg>
    ),
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-200',
    description: 'Projects, issues, and merge requests',
    setupUrl: 'https://docs.gitlab.com/ee/integration/oauth_provider.html',
  },
  SLACK: {
    name: 'Slack',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none">
        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" fill="#E01E5A"/>
      </svg>
    ),
    color: 'text-[#E01E5A]',
    bgColor: 'bg-pink-50',
    borderColor: 'border-pink-200',
    description: 'Messages and workspace data',
    setupUrl: 'https://api.slack.com/apps',
  },
  gmail: {
    name: 'Gmail',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24">
        <path fill="#EA4335" d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z"/>
      </svg>
    ),
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    description: 'Email sync for knowledge base',
    setupUrl: 'https://console.cloud.google.com/apis/credentials',
  },
  zoom: {
    name: 'Zoom',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="#2D8CFF">
        <path d="M4.585 6.515h9.88c1.636 0 2.963 1.327 2.963 2.963v5.922c0 1.636-1.327 2.963-2.963 2.963H4.585c-1.636 0-2.963-1.327-2.963-2.963V9.478c0-1.636 1.327-2.963 2.963-2.963zm14.17 2.222v6.526l3.623 2.417V6.32l-3.623 2.417z"/>
      </svg>
    ),
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    description: 'Video meetings and recordings',
    setupUrl: 'https://marketplace.zoom.us/develop/create',
  },
  google_calendar: {
    name: 'Google Calendar',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M19.5 3h-15A1.5 1.5 0 003 4.5v15A1.5 1.5 0 004.5 21h15a1.5 1.5 0 001.5-1.5v-15A1.5 1.5 0 0019.5 3zM12 18a6 6 0 110-12 6 6 0 010 12z"/>
        <path fill="#EA4335" d="M12 8v4l3 3"/>
      </svg>
    ),
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    description: 'Calendar events and schedules',
    setupUrl: 'https://console.cloud.google.com/apis/credentials',
  },
  google_drive: {
    name: 'Google Drive',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M12.01 1.485c-2.082 0-3.754.02-3.743.047.01.02 1.708 3.001 3.774 6.62l3.76 6.574h3.76c2.07 0 3.76-.019 3.76-.04 0-.02-1.686-2.994-3.745-6.607L15.81 1.532c-.018-.04-1.72-.047-3.8-.047z"/>
        <path fill="#0F9D58" d="M1.485 14.869l3.76 6.574c.02.034 3.728.057 8.24.057h8.2l-3.76-6.574c-.02-.034-3.728-.057-8.24-.057h-8.2z"/>
        <path fill="#FFCD40" d="M8.267 1.532L.505 14.869h7.52L15.81 1.532h-7.54z"/>
      </svg>
    ),
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-50',
    borderColor: 'border-yellow-200',
    description: 'Files and document storage',
    setupUrl: 'https://console.cloud.google.com/apis/credentials',
  },
  TELEGRAM: {
    name: 'Telegram',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="#0088cc">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
      </svg>
    ),
    color: 'text-sky-600',
    bgColor: 'bg-sky-50',
    borderColor: 'border-sky-200',
    description: 'Telegram messages and channels',
    setupUrl: 'https://core.telegram.org/bots#botfather',
  },
  onepassword: {
    name: '1Password',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="#0094F5">
        <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm0 3.6c4.64 0 8.4 3.76 8.4 8.4s-3.76 8.4-8.4 8.4-8.4-3.76-8.4-8.4 3.76-8.4 8.4-8.4zm0 2.4a6 6 0 100 12 6 6 0 000-12zm0 2.4a3.6 3.6 0 110 7.2 3.6 3.6 0 010-7.2z"/>
      </svg>
    ),
    color: 'text-[#0094F5]',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    description: 'Secure credential & secret management',
    setupUrl: 'https://developer.1password.com/docs/service-accounts/',
  },
  mailisk: {
    name: 'Mailisk',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none">
        <rect width="24" height="24" rx="6" fill="#111827" />
        <path d="M5 8.5A1.5 1.5 0 0 1 6.5 7h11A1.5 1.5 0 0 1 19 8.5v7A1.5 1.5 0 0 1 17.5 17h-11A1.5 1.5 0 0 1 5 15.5v-7Z" stroke="#F9FAFB" strokeWidth="1.5"/>
        <path d="m6 8 6 4.5L18 8" stroke="#F97316" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M8 19h8" stroke="#F9FAFB" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
    color: 'text-orange-700',
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-200',
    description: 'Disposable inboxes for automated signup and OTP verification tests',
    setupUrl: 'https://docs.mailisk.com/',
  },
  jira: {
    name: 'Jira',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="#0052CC">
        <path d="M11.571 11.513H0a5.218 5.218 0 005.232 5.215h2.13v2.057A5.215 5.215 0 0012.575 24V12.518a1.005 1.005 0 00-1.005-1.005zm5.723-5.756H5.736a5.215 5.215 0 005.215 5.214h2.129v2.058a5.218 5.218 0 005.215 5.214V6.758a1.001 1.001 0 00-1.001-1.001zM23.013 0H11.455a5.215 5.215 0 005.215 5.215h2.129v2.057A5.215 5.215 0 0024 12.483V1.005A1.009 1.009 0 0023.013 0z"/>
      </svg>
    ),
    color: 'text-[#0052CC]',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    description: 'Issues, projects, and sprints',
    setupUrl: 'https://developer.atlassian.com/console/myapps/',
  },
  clickup: {
    name: 'ClickUp',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24">
        <path fill="#7B68EE" d="M4.105 18.214l3.06-2.392c1.577 2.05 3.071 2.94 4.835 2.94 1.764 0 3.258-.89 4.835-2.94l3.06 2.392C17.428 21.313 14.86 22.762 12 22.762c-2.86 0-5.428-1.449-7.895-4.548z"/>
        <path fill="#49CCF9" d="M12 6.238L6.84 11.93l-2.735-2.5L12 1.238l7.895 8.192-2.735 2.5z"/>
      </svg>
    ),
    color: 'text-[#7B68EE]',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    description: 'Tasks, docs, and project management',
    setupUrl: 'https://clickup.com/integrations',
  },
  twitter: {
    name: 'Twitter / X',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
      </svg>
    ),
    color: 'text-gray-900',
    bgColor: 'bg-gray-100',
    borderColor: 'border-gray-200',
    description: 'Posts, mentions, and social engagement',
    setupUrl: 'https://developer.twitter.com/en/portal/dashboard',
  },
  linkedin: {
    name: 'LinkedIn',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="#0A66C2">
        <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
      </svg>
    ),
    color: 'text-[#0A66C2]',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    description: 'Professional networking and posts',
    setupUrl: 'https://www.linkedin.com/developers/apps',
  },
  recall: {
    name: 'Recall.ai',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="#6366F1">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
      </svg>
    ),
    color: 'text-indigo-600',
    bgColor: 'bg-indigo-50',
    borderColor: 'border-indigo-200',
    description: 'Meeting bots for Zoom, Meet, Teams & Slack',
    setupUrl: 'https://www.recall.ai/dashboard',
  },
  zendesk: {
    name: 'Zendesk',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="#03363D">
        <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm-1.5 17.25L4.5 9h13l-6 8.25zm1.5-9.75c-2.07 0-3.75-1.68-3.75-3.75S9.93 0 12 0s3.75 1.68 3.75 3.75S14.07 7.5 12 7.5z"/>
      </svg>
    ),
    color: 'text-[#03363D]',
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200',
    description: 'Tickets, users, and support conversations',
    setupUrl: 'https://developer.zendesk.com/documentation/live-chat/getting-started/oauth-authentication/',
  },
  zoho_crm: {
    name: 'Zoho CRM',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none">
        <rect width="24" height="24" rx="4" fill="#E42527"/>
        <path d="M4 16l5-8h6l-5 8H4z" fill="white"/>
        <path d="M11 16l5-8h4l-5 8h-4z" fill="white" fillOpacity="0.6"/>
      </svg>
    ),
    color: 'text-[#E42527]',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    description: 'Contacts, leads, deals, and CRM data',
    setupUrl: 'https://www.zoho.com/crm/developer/docs/api/v6/oauth-overview.html',
  },
  kling: {
    name: 'Kling AI',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none">
        <rect width="24" height="24" rx="6" fill="#7C3AED"/>
        <path d="M8 7.5C8 7.22 8.22 7 8.5 7h2c.28 0 .5.22.5.5v9c0 .28-.22.5-.5.5h-2A.5.5 0 0 1 8 16.5v-9Z" fill="white"/>
        <path d="M13 9.27c0-.45.5-.7.87-.44l4.26 3.23c.3.23.3.67 0 .9L13.87 16.2c-.37.27-.87.01-.87-.44V9.27Z" fill="white"/>
      </svg>
    ),
    color: 'text-purple-700',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    description: 'AI video generation from text prompts (9:16 vertical)',
    setupUrl: 'https://klingai.com/dev',
  },
  minimax_video: {
    name: 'Minimax Hailuo',
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none">
        <rect width="24" height="24" rx="6" fill="#2563EB"/>
        <circle cx="12" cy="12" r="5" stroke="white" strokeWidth="1.5"/>
        <path d="M10 10l4 2-4 2V10Z" fill="white"/>
      </svg>
    ),
    color: 'text-blue-700',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    description: 'High-quality AI video generation',
    setupUrl: 'https://www.minimaxi.com/en/document-center',
  },
}

type TabType = 'my-connections' | 'admin'

export default function OAuthAppsPage() {
  const [apps, setApps] = useState<OAuthApp[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [platformApps, setPlatformApps] = useState<any[]>([])
  const [loadingPlatformApps, setLoadingPlatformApps] = useState(false)
  const [userConnections, setUserConnections] = useState<Record<number, UserConnection>>({})
  const [loadingConnections, setLoadingConnections] = useState(false)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabType>('my-connections')
  const [apiTokenModal, setApiTokenModal] = useState<{ open: boolean; app: OAuthApp | null }>({ open: false, app: null })
  const [apiTokenInput, setApiTokenInput] = useState('')
  const [savingApiToken, setSavingApiToken] = useState(false)
  const [copiedWebhook, setCopiedWebhook] = useState<number | null>(null)

  // Get webhook URL for Recall.ai
  const getWebhookUrl = () => {
    return `${API_URL}/api/webhooks/recall`
  }

  // Copy webhook URL to clipboard
  const copyWebhookUrl = async (appId: number) => {
    try {
      await navigator.clipboard.writeText(getWebhookUrl())
      setCopiedWebhook(appId)
      setTimeout(() => setCopiedWebhook(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  useEffect(() => {
    fetchOAuthApps()
    fetchPlatformApps()
  }, [])

  useEffect(() => {
    if (apps.length > 0) {
      fetchUserConnections()
    }
  }, [apps])

  const fetchOAuthApps = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getOAuthApps()
      setApps(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const fetchPlatformApps = async () => {
    try {
      setLoadingPlatformApps(true)
      const data = await apiClient.getPlatformOAuthApps()
      setPlatformApps(data)
    } catch (err) {
      console.error('Failed to fetch platform apps:', err)
    } finally {
      setLoadingPlatformApps(false)
    }
  }

  const handleConnectPlatformApp = async (platformApp: any) => {
    try {
      setError(null)
      // Use AJAX initiate so Authorization header is sent → tenant_id in state → clone created
      const result = await apiClient.initiateOAuth(platformApp.id, window.location.href, false)
      window.location.href = result.auth_url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to initiate OAuth connection')
    }
  }

  const handleDisconnectPlatformApp = async (provider: string) => {
    const clone = apps.find(a => a.source === 'platform' && a.provider.toLowerCase() === provider.toLowerCase())
    if (clone) {
      await handleDelete(clone.id)
      await fetchPlatformApps()
    }
  }

  const fetchUserConnections = async () => {
    try {
      setLoadingConnections(true)
      const connections: Record<number, UserConnection> = {}

      await Promise.all(
        apps.map(async (app) => {
          try {
            const status = await apiClient.getUserConnectionStatus(app.id)
            connections[app.id] = {
              ...status,
              auth_method: status.auth_method
            }
          } catch (err) {
            connections[app.id] = { app_id: app.id, connected: false }
          }
        })
      )

      setUserConnections(connections)
    } catch (err) {
      console.error('Failed to fetch user connections:', err)
    } finally {
      setLoadingConnections(false)
    }
  }

  const handleDelete = async (appId: number) => {
    try {
      await apiClient.deleteOAuthApp(appId)
      setApps(apps.filter(app => app.id !== appId))
      setDeleteConfirm(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    }
  }

  const handleAuthorize = async (app: OAuthApp, userLevel: boolean = false) => {
    const authMethod = userConnections[app.id]?.auth_method || app.auth_method || 'oauth'

    if (userLevel && authMethod === 'api_token') {
      // API token apps: Show modal to enter token
      setApiTokenModal({ open: true, app })
      setApiTokenInput('')
    } else if (userLevel) {
      // User-level OAuth: Use secure AJAX-based initiation
      try {
        const result = await apiClient.initiateOAuth(app.id, window.location.href, true)
        window.location.href = result.auth_url
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to initiate OAuth')
      }
    } else {
      // App-level OAuth: Direct redirect (admin flow, no user context needed)
      const redirectUrl = encodeURIComponent(window.location.href)
      const authUrl = `${API_URL}/api/v1/oauth/${app.provider.toLowerCase()}/authorize?oauth_app_id=${app.id}&redirect_url=${redirectUrl}&user_level=false`
      window.location.href = authUrl
    }
  }

  const handleSaveApiToken = async () => {
    if (!apiTokenModal.app || !apiTokenInput.trim()) {
      setError('Please enter an API token')
      return
    }

    setSavingApiToken(true)
    try {
      await apiClient.saveUserApiToken(apiTokenModal.app.id, apiTokenInput.trim())
      setApiTokenModal({ open: false, app: null })
      setApiTokenInput('')
      // Reload connections to reflect the change
      fetchUserConnections()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save API token')
    } finally {
      setSavingApiToken(false)
    }
  }

  const handleDisconnectUser = async (tokenId: string, appId: number) => {
    try {
      setDisconnecting(tokenId)
      await apiClient.deleteUserOAuthToken(tokenId)
      setUserConnections(prev => ({
        ...prev,
        [appId]: { ...prev[appId], connected: false, user_token: undefined }
      }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect')
    } finally {
      setDisconnecting(null)
    }
  }

  const isAuthorized = (app: OAuthApp) => {
    if (app.auth_method === 'api_token') return app.has_api_token
    if (app.auth_method === 'basic_auth') return app.has_api_token // password stored = configured
    if (app.auth_method === 'github_app') return app.has_private_key // App ID + private key stored = configured
    return app.has_access_token
  }

  const isUserConnected = (appId: number) => {
    return userConnections[appId]?.connected || false
  }

  const getUserConnection = (appId: number) => {
    return userConnections[appId]?.user_token
  }

  const getConfig = (provider: string) => {
    return PROVIDER_CONFIG[provider] || {
      name: provider,
      icon: <Settings className="w-5 h-5" />,
      color: 'text-gray-600',
      bgColor: 'bg-gray-100',
      borderColor: 'border-gray-200',
      description: '',
      setupUrl: '#',
    }
  }


  if (loading) {
    return (
      <div className="dashboard-resource-page flex min-h-screen items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-semibold tracking-[-0.04em] text-gray-950 md:text-[2rem]">Integrations</h1>
          <p className="text-gray-500 mt-1 text-sm">
            Connect your accounts to enable tools and data syncing
          </p>
        </div>

        {error && (
          <div className="mb-5">
            <ErrorAlert message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1.5 mb-6 rounded-[0.45rem] border border-black/10 bg-white/80 p-1.5 shadow-[0_12px_28px_rgba(0,0,0,0.04)] w-fit">
          <button
            onClick={() => setActiveTab('my-connections')}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-[0.35rem] transition-colors ${
              activeTab === 'my-connections'
                ? 'bg-[#171717] text-white shadow-[0_10px_22px_rgba(0,0,0,0.12)]'
                : 'text-gray-600 hover:bg-[#f7f2e7] hover:text-[#171717]'
            }`}
          >
            <User className="w-4 h-4" />
            My Connections
          </button>
          <button
            onClick={() => setActiveTab('admin')}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-[0.35rem] transition-colors ${
              activeTab === 'admin'
                ? 'bg-[#171717] text-white shadow-[0_10px_22px_rgba(0,0,0,0.12)]'
                : 'text-gray-600 hover:bg-[#f7f2e7] hover:text-[#171717]'
            }`}
          >
            <Shield className="w-4 h-4" />
            Admin Setup
          </button>
        </div>

        {/* My Connections Tab */}
        {activeTab === 'my-connections' && (
          <div className="space-y-4">
            {apps.length === 0 ? (
              <div className="rounded-[0.5rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] shadow-[0_24px_60px_-46px_rgba(73,45,23,0.3)] p-10 text-center">
                <div className="w-12 h-12 bg-[#f3ecde] rounded-full flex items-center justify-center mx-auto mb-4">
                  <Link2 className="w-6 h-6 text-[#7c5d45]" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">No integrations available</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Ask your admin to set up OAuth apps before you can connect your accounts.
                </p>
              </div>
            ) : (
              <div className="grid gap-2">
                {apps.map((app) => {
                  const config = getConfig(app.provider)
                  const connStatus = userConnections[app.id]
                  const isAdminShared = connStatus?.admin_connected === true
                  const userConnected = isUserConnected(app.id)
                  const userConnection = getUserConnection(app.id)

                  return (
                    <div
                      key={app.id}
                      className="rounded-[0.5rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] shadow-[0_24px_60px_-46px_rgba(73,45,23,0.3)] p-4 hover:border-[#cdb79d] transition-all"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 ${config.bgColor} rounded-[0.45rem] flex items-center justify-center`}>
                            {config.icon}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <h3 className="font-semibold text-gray-900">{config.name}</h3>
                              <span className="text-xs text-[#7c5d45]">({app.app_name})</span>
                              {isAdminShared && (
                                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-[#f3ecde] border border-[#dfd1be] text-[#7c5d45] text-xs font-semibold rounded-[0.3rem]">
                                  <Shield className="w-3 h-3" />
                                  Admin
                                </span>
                              )}
                            </div>
                            {isAdminShared ? (
                              <p className="text-sm text-emerald-600 flex items-center gap-1">
                                <CheckCircle className="w-3.5 h-3.5" />
                                Connected via admin setup
                              </p>
                            ) : userConnected && userConnection ? (
                              <p className="text-sm text-emerald-600 flex items-center gap-1">
                                <CheckCircle className="w-3.5 h-3.5" />
                                {userConnection.provider_email || userConnection.provider_username || 'Connected'}
                              </p>
                            ) : (
                              <p className="text-sm text-gray-500">{config.description}</p>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          {loadingConnections ? (
                            <span className="text-xs text-[#7c5d45]">Loading...</span>
                          ) : isAdminShared ? (
                            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-[0.4rem]">
                              <CheckCircle className="w-4 h-4" />
                              Connected
                            </span>
                          ) : userConnected ? (
                            <button
                              onClick={() => userConnection?.id && handleDisconnectUser(userConnection.id, app.id)}
                              disabled={disconnecting === userConnection?.id}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold text-[#7c5d45] border border-[#dbcdb9] bg-white rounded-[0.4rem] hover:bg-[#f7f2e7] transition-colors disabled:opacity-50"
                            >
                              <Unlink className="w-4 h-4" />
                              {disconnecting === userConnection?.id ? 'Disconnecting...' : 'Disconnect'}
                            </button>
                          ) : (
                            <button
                              onClick={() => handleAuthorize(app, true)}
                              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white bg-[#171717] rounded-[0.4rem] hover:bg-[#2a2a2a] transition-colors shadow-[0_10px_22px_rgba(0,0,0,0.12)]"
                            >
                              <Link2 className="w-4 h-4" />
                              {app.auth_method === 'api_token' ? 'Add Token' : 'Connect'}
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* Admin Setup Tab */}
        {activeTab === 'admin' && (
          <div className="space-y-6">
            {/* Platform Integrations */}
            {(platformApps.length > 0 || loadingPlatformApps) && (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-[#7c5d45]" />
                  <h2 className="text-xs font-semibold text-[#7c5d45] uppercase tracking-[0.12em]">Platform Integrations</h2>
                  <span className="text-xs text-gray-400 font-normal normal-case">— credentials managed by Synkora</span>
                </div>
                {loadingPlatformApps ? (
                  <div className="text-sm text-[#7c5d45] py-2">Loading platform apps...</div>
                ) : (
                  <div className="space-y-2">
                    {platformApps.map((platformApp) => {
                      const config = getConfig(platformApp.provider)
                      const isConnected = apps.some(
                        a => a.source === 'platform' && a.provider.toLowerCase() === platformApp.provider.toLowerCase()
                      )
                      return (
                        <div key={platformApp.id} className="rounded-[0.5rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] shadow-[0_24px_60px_-46px_rgba(73,45,23,0.3)] p-4 hover:border-[#cdb79d] transition-all">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className={`w-9 h-9 ${config.bgColor} rounded-[0.45rem] flex items-center justify-center`}>
                                {config.icon}
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <h3 className="font-semibold text-gray-900">{config.name || platformApp.app_name}</h3>
                                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-[#f3ecde] border border-[#dfd1be] text-[#7c5d45] text-xs font-semibold rounded-[0.3rem]">
                                    <Shield className="w-3 h-3" />
                                    Platform
                                  </span>
                                </div>
                                <p className="text-xs text-gray-500">{config.description || platformApp.description}</p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              {isConnected ? (
                                <>
                                  <span className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-[0.4rem]">
                                    <CheckCircle className="w-4 h-4" />
                                    Connected
                                  </span>
                                  <button
                                    onClick={() => handleDisconnectPlatformApp(platformApp.provider)}
                                    className="p-2 text-[#7c5d45] hover:text-primary-600 hover:bg-primary-50 rounded-[0.4rem] transition-colors"
                                    title="Disconnect"
                                  >
                                    <Unlink className="w-4 h-4" />
                                  </button>
                                </>
                              ) : (
                                <button
                                  onClick={() => handleConnectPlatformApp(platformApp)}
                                  className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white bg-[#171717] rounded-[0.4rem] hover:bg-[#2a2a2a] transition-colors shadow-[0_10px_22px_rgba(0,0,0,0.12)]"
                                >
                                  <Link2 className="w-4 h-4" />
                                  Connect
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Header with Add Button */}
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold text-[#7c5d45] uppercase tracking-[0.12em]">
                Custom Integrations
              </h2>
              <Link
                href="/oauth-apps/create"
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white bg-[#171717] hover:bg-[#2a2a2a] rounded-[0.4rem] shadow-[0_10px_22px_rgba(0,0,0,0.12)] transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add New
              </Link>
            </div>

            {/* Configured Apps */}
            {apps.filter(a => a.source !== 'platform').length > 0 ? (
              <div className="space-y-2">
                {apps.filter(a => a.source !== 'platform').map((app) => {
                  const config = getConfig(app.provider)
                  const authorized = isAuthorized(app)

                  return (
                    <div
                      key={app.id}
                      className="rounded-[0.5rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] shadow-[0_24px_60px_-46px_rgba(73,45,23,0.3)] p-4 hover:border-[#cdb79d] transition-all"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`w-9 h-9 ${config.bgColor} rounded-[0.45rem] flex items-center justify-center`}>
                            {config.icon}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <h3 className="font-semibold text-gray-900">{app.app_name}</h3>
                              {app.is_default && (
                                <span className="px-1.5 py-0.5 bg-[#f3ecde] border border-[#dfd1be] text-[#7c5d45] text-xs font-semibold rounded-[0.3rem]">
                                  Default
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2 text-xs text-gray-500">
                              <span>{config.name}</span>
                              <span>·</span>
                              {authorized ? (
                                <span className="text-emerald-600 flex items-center gap-1">
                                  <CheckCircle className="w-3 h-3" />
                                  {app.auth_method === 'basic_auth' || app.auth_method === 'github_app' ? 'Configured' : 'Authorized'}
                                </span>
                              ) : app.auth_method === 'basic_auth' || app.auth_method === 'github_app' ? (
                                <span className="text-amber-600 flex items-center gap-1">
                                  <AlertCircle className="w-3 h-3" />
                                  Missing Credentials
                                </span>
                              ) : (
                                <span className="text-amber-600 flex items-center gap-1">
                                  <AlertCircle className="w-3 h-3" />
                                  Needs Authorization
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-1">
                          {!authorized && app.auth_method !== 'basic_auth' && app.auth_method !== 'github_app' && (
                            <button
                              onClick={() => handleAuthorize(app, false)}
                              className="px-3 py-1.5 text-sm font-semibold text-white bg-[#171717] rounded-[0.4rem] hover:bg-[#2a2a2a] transition-colors"
                            >
                              Authorize
                            </button>
                          )}
                          <Link
                            href={`/oauth-apps/${app.id}/edit`}
                            className="p-2 text-[#7c5d45] hover:text-gray-900 hover:bg-[#f3ecde] rounded-[0.4rem] transition-colors"
                            title="Edit"
                          >
                            <Settings className="w-4 h-4" />
                          </Link>
                          {deleteConfirm === app.id ? (
                            <div className="flex items-center gap-1 ml-1">
                              <button
                                onClick={() => handleDelete(app.id)}
                                className="px-2 py-1 text-xs font-semibold text-white bg-primary-600 rounded-[0.3rem] hover:bg-primary-700 transition-colors"
                              >
                                Delete
                              </button>
                              <button
                                onClick={() => setDeleteConfirm(null)}
                                className="px-2 py-1 text-xs font-semibold text-[#7c5d45] border border-[#dbcdb9] bg-white rounded-[0.3rem] hover:bg-[#f7f2e7] transition-colors"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setDeleteConfirm(app.id)}
                              className="p-2 text-[#7c5d45] hover:text-primary-600 hover:bg-primary-50 rounded-[0.4rem] transition-colors"
                              title="Delete"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Webhook URL for Recall.ai */}
                      {app.provider.toLowerCase() === 'recall' && (
                        <div className="mt-3 pt-3 border-t border-[#e5d9ca]">
                          <div className="flex items-center gap-2 mb-2">
                            <Webhook className="w-4 h-4 text-[#7c5d45]" />
                            <span className="text-xs font-semibold text-[#7c5d45]">Webhook URL</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <code className="flex-1 px-3 py-2 bg-[#f7f2e7] border border-[#e5d9ca] rounded-[0.4rem] text-xs text-gray-700 font-mono truncate">
                              {getWebhookUrl()}
                            </code>
                            <button
                              onClick={() => copyWebhookUrl(app.id)}
                              className={`p-2 rounded-[0.4rem] transition-colors ${
                                copiedWebhook === app.id
                                  ? 'bg-emerald-100 text-emerald-600'
                                  : 'bg-[#f3ecde] text-[#7c5d45] hover:bg-[#eadfce]'
                              }`}
                              title={copiedWebhook === app.id ? 'Copied!' : 'Copy URL'}
                            >
                              {copiedWebhook === app.id ? (
                                <Check className="w-4 h-4" />
                              ) : (
                                <Copy className="w-4 h-4" />
                              )}
                            </button>
                          </div>
                          <p className="text-xs text-gray-500 mt-2">
                            Add this URL to your Recall.ai dashboard to receive meeting events (bot status, transcripts, etc.)
                          </p>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="rounded-[0.5rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] shadow-[0_24px_60px_-46px_rgba(73,45,23,0.3)] p-10 text-center">
                <div className="w-12 h-12 bg-[#f3ecde] rounded-full flex items-center justify-center mx-auto mb-4">
                  <Plus className="w-6 h-6 text-[#7c5d45]" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">No custom integrations yet</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Add your own OAuth app credentials to use your own developer app instead of the platform-provided one.
                </p>
                <Link
                  href="/oauth-apps/create"
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white bg-[#171717] hover:bg-[#2a2a2a] rounded-[0.4rem] shadow-[0_10px_22px_rgba(0,0,0,0.12)] transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  Add Custom Integration
                </Link>
              </div>
            )}

            {/* Setup Guide */}
            <div className="rounded-[0.5rem] border border-[#e5d9ca] bg-[#f7f2e7] p-4">
              <h3 className="text-sm font-semibold text-[#7c5d45] mb-2">Setup Guide</h3>
              <ol className="text-sm text-gray-600 space-y-1.5 list-decimal list-inside">
                <li>Create an OAuth app in the provider's developer console</li>
                <li>Copy the Client ID and Client Secret</li>
                <li>Add the credentials here and authorize the app</li>
                <li>Users can then connect their own accounts</li>
              </ol>
              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(PROVIDER_CONFIG).map(([key, config]) => (
                  <a
                    key={key}
                    href={config.setupUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-[#7c5d45] hover:text-primary-600 transition-colors"
                  >
                    <ExternalLink className="w-3 h-3" />
                    {config.name} Docs
                  </a>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* API Token Modal */}
        {apiTokenModal.open && apiTokenModal.app && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="rounded-[0.5rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.99),_rgba(249,245,239,0.98))] shadow-[0_40px_80px_-20px_rgba(73,45,23,0.35)] max-w-md w-full mx-4 overflow-hidden">
              <div className="px-6 py-4 border-b border-[#e5d9ca] flex items-center justify-between">
                <h3 className="text-base font-semibold text-gray-900">
                  Add Your {getConfig(apiTokenModal.app.provider).name} API Token
                </h3>
                <button
                  onClick={() => setApiTokenModal({ open: false, app: null })}
                  className="text-[#7c5d45] hover:text-gray-900 p-1 hover:bg-[#f3ecde] rounded-[0.3rem] transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <div className="px-6 py-4">
                <p className="text-sm text-gray-600 mb-4">
                  Enter your personal API token for {getConfig(apiTokenModal.app.provider).name}. This token will be used for your account only.
                </p>
                <label className="block text-xs font-semibold text-[#7c5d45] uppercase tracking-[0.08em] mb-2">
                  API Token
                </label>
                <input
                  type="password"
                  value={apiTokenInput}
                  onChange={(e) => setApiTokenInput(e.target.value)}
                  placeholder="Enter your API token"
                  className="w-full px-3 py-2 border border-[#dbcdb9] bg-white rounded-[0.4rem] focus:ring-2 focus:ring-[#79dfbc] focus:border-transparent text-sm outline-none transition-shadow"
                />
                <p className="mt-2 text-xs text-gray-500">
                  Your token is encrypted and stored securely.
                </p>
              </div>
              <div className="px-6 py-4 border-t border-[#e5d9ca] flex justify-end gap-2">
                <button
                  onClick={() => setApiTokenModal({ open: false, app: null })}
                  className="px-4 py-2 text-sm font-semibold text-[#7c5d45] border border-[#dbcdb9] bg-white hover:bg-[#f7f2e7] rounded-[0.4rem] transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveApiToken}
                  disabled={savingApiToken || !apiTokenInput.trim()}
                  className="px-4 py-2 text-sm font-semibold text-white bg-[#171717] hover:bg-[#2a2a2a] rounded-[0.4rem] transition-colors shadow-[0_10px_22px_rgba(0,0,0,0.12)] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {savingApiToken ? 'Saving...' : 'Save Token'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
