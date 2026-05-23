'use client'

import { Plus } from 'lucide-react'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import { apiClient } from '@/lib/api/client'
import DashboardPageShell from '@/components/dashboard/DashboardPageShell'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

// Brand icons as React components
const GitHubIcon = () => (
  <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
    <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
  </svg>
)

const SlackIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" fill="#E01E5A"/>
  </svg>
)

const GmailIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24">
    <path fill="#EA4335" d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z"/>
  </svg>
)

const ZoomIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="4" fill="#2D8CFF"/>
    <path d="M5 7.5C5 6.67 5.67 6 6.5 6H13.5C14.33 6 15 6.67 15 7.5V12.5C15 13.33 14.33 14 13.5 14H6.5C5.67 14 5 13.33 5 12.5V7.5Z" fill="white"/>
    <path d="M15.5 8.5L19 6V14L15.5 11.5V8.5Z" fill="white"/>
    <path d="M5 16H19V17C19 17.55 18.55 18 18 18H6C5.45 18 5 17.55 5 17V16Z" fill="white"/>
  </svg>
)

const GoogleCalendarIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24">
    <path fill="#4285F4" d="M19.5 4h-3V2.5a.5.5 0 0 0-1 0V4h-7V2.5a.5.5 0 0 0-1 0V4h-3A2.5 2.5 0 0 0 2 6.5v13A2.5 2.5 0 0 0 4.5 22h15a2.5 2.5 0 0 0 2.5-2.5v-13A2.5 2.5 0 0 0 19.5 4z"/>
    <path fill="#fff" d="M4 9h16v10.5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19.5V9z"/>
    <path fill="#EA4335" d="M8 12h2v2H8zM8 15h2v2H8z"/>
    <path fill="#34A853" d="M11 12h2v2h-2zM11 15h2v2h-2z"/>
    <path fill="#FBBC04" d="M14 12h2v2h-2zM14 15h2v2h-2z"/>
  </svg>
)

const GoogleDriveIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24">
    <path fill="#4285F4" d="M22.5 15.5l-3-5.19L12 .5l-3 5.19 7.5 9.81h6z"/>
    <path fill="#00A86B" d="M7.5 15.5L1.5 15.5l3-5.19 7.5-9.81 3 5.19-7.5 9.81z"/>
    <path fill="#FFBA00" d="M1.5 15.5h21l-3 5.19H4.5l-3-5.19z"/>
  </svg>
)

const ClickUpIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <linearGradient id="clickup-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stopColor="#8930FD"/>
      <stop offset="50%" stopColor="#49CCF9"/>
      <stop offset="100%" stopColor="#7FD88A"/>
    </linearGradient>
    <path d="M4 16.5L7.5 13.5L12 17L16.5 13.5L20 16.5L12 23L4 16.5Z" fill="url(#clickup-gradient)"/>
    <path d="M12 1L4 10L7.5 13L12 8L16.5 13L20 10L12 1Z" fill="url(#clickup-gradient)"/>
  </svg>
)

const JiraIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24">
    <defs>
      <linearGradient id="jira-gradient-1" x1="98.031%" x2="58.888%" y1="0.161%" y2="40.766%">
        <stop offset="18%" stopColor="#0052CC"/>
        <stop offset="100%" stopColor="#2684FF"/>
      </linearGradient>
      <linearGradient id="jira-gradient-2" x1="100.665%" x2="55.402%" y1="0.455%" y2="44.727%">
        <stop offset="18%" stopColor="#0052CC"/>
        <stop offset="100%" stopColor="#2684FF"/>
      </linearGradient>
    </defs>
    <path fill="#2684FF" d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005z"/>
    <path fill="url(#jira-gradient-1)" d="M17.303 5.768H5.732a5.215 5.215 0 0 0 5.213 5.215h2.13v2.057a5.215 5.215 0 0 0 5.213 5.214V6.773a1.005 1.005 0 0 0-1.005-1.005h.02z"/>
    <path fill="url(#jira-gradient-2)" d="M23.035 0H11.464a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.218 5.218 0 0 0 24.04 12.49V1.005A1.005 1.005 0 0 0 23.035 0z"/>
  </svg>
)

const GitLabIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <path fill="#E24329" d="M12 22.1L15.9 11H8.1L12 22.1Z"/>
    <path fill="#FC6D26" d="M12 22.1L8.1 11H1.3L12 22.1Z"/>
    <path fill="#FCA326" d="M1.3 11L0 14.9C-0.1 15.3 0.1 15.7 0.5 15.9L12 22.1L1.3 11Z"/>
    <path fill="#E24329" d="M1.3 11H8.1L5.2 1.9C5 1.4 4.3 1.4 4.1 1.9L1.3 11Z"/>
    <path fill="#FC6D26" d="M12 22.1L15.9 11H22.7L12 22.1Z"/>
    <path fill="#FCA326" d="M22.7 11L24 14.9C24.1 15.3 23.9 15.7 23.5 15.9L12 22.1L22.7 11Z"/>
    <path fill="#E24329" d="M22.7 11H15.9L18.8 1.9C19 1.4 19.7 1.4 19.9 1.9L22.7 11Z"/>
  </svg>
)

const TelegramIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="#0088cc">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
  </svg>
)

const OnePasswordIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="#0094F5">
    <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm0 3.6c4.64 0 8.4 3.76 8.4 8.4s-3.76 8.4-8.4 8.4-8.4-3.76-8.4-8.4 3.76-8.4 8.4-8.4zm0 2.4a6 6 0 100 12 6 6 0 000-12zm0 2.4a3.6 3.6 0 110 7.2 3.6 3.6 0 010-7.2z"/>
  </svg>
)

const MailiskIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="6" fill="#111827" />
    <path d="M5 8.5A1.5 1.5 0 0 1 6.5 7h11A1.5 1.5 0 0 1 19 8.5v7A1.5 1.5 0 0 1 17.5 17h-11A1.5 1.5 0 0 1 5 15.5v-7Z" stroke="#F9FAFB" strokeWidth="1.5"/>
    <path d="m6 8 6 4.5L18 8" stroke="#F97316" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M8 19h8" stroke="#F9FAFB" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
)

const TwitterIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="currentColor">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
  </svg>
)

const LinkedInIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="#0A66C2">
    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
  </svg>
)

const RecallIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="6" fill="#6366F1"/>
    <circle cx="12" cy="12" r="5" stroke="white" strokeWidth="2"/>
    <circle cx="12" cy="12" r="2" fill="white"/>
    <path d="M12 4V7M12 17V20M4 12H7M17 12H20" stroke="white" strokeWidth="2" strokeLinecap="round"/>
  </svg>
)

const MicromobilityIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="6" fill="#10B981"/>
    <circle cx="6.5" cy="17" r="2.5" stroke="white" strokeWidth="1.5"/>
    <circle cx="17.5" cy="17" r="2.5" stroke="white" strokeWidth="1.5"/>
    <path d="M6.5 17H11L14 8H17.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M12 8H16" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
    <circle cx="17.5" cy="8" r="1" fill="white"/>
  </svg>
)

const OpenWeatherIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="6" fill="#EB6E4B"/>
    <circle cx="12" cy="10" r="3.5" stroke="white" strokeWidth="1.5"/>
    <path d="M12 4V5.5M12 14.5V16M6 10H4.5M19.5 10H18M7.93 6.93L6.87 5.87M17.13 17.13L16.07 16.07M7.93 13.07L6.87 14.13M17.13 6.93L16.07 7.99" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
    <path d="M7 17.5C7 16.12 8.12 15 9.5 15H16.5C17.88 15 19 16.12 19 17.5C19 18.88 17.88 20 16.5 20H9.5C8.12 20 7 18.88 7 17.5Z" fill="white" fillOpacity="0.9"/>
  </svg>
)

const PredictHQIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="6" fill="#6366F1"/>
    <path d="M4 18L8 12L12 15L16 8L20 11" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    <circle cx="20" cy="6" r="2" fill="white"/>
  </svg>
)

const TicketmasterIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="6" fill="#026CDF"/>
    <rect x="3" y="8" width="18" height="8" rx="2" fill="white" fillOpacity="0.15" stroke="white" strokeWidth="1.5"/>
    <circle cx="3" cy="12" r="2" fill="#026CDF" stroke="white" strokeWidth="1.5"/>
    <circle cx="21" cy="12" r="2" fill="#026CDF" stroke="white" strokeWidth="1.5"/>
    <path d="M10 11h4M10 13h2" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
)

const MapboxIcon = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
    <rect width="24" height="24" rx="6" fill="#000000"/>
    <circle cx="12" cy="12" r="7" stroke="white" strokeWidth="1.5"/>
    <circle cx="12" cy="12" r="2.5" fill="white"/>
    <path d="M12 5V7M12 17V19M5 12H7M17 12H19" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
)

const PROVIDERS = [
  {
    value: 'github',
    label: 'GitHub',
    icon: <GitHubIcon />,
    color: 'text-gray-900',
    bgColor: 'bg-gray-100',
    description: 'Access repositories, issues, and pull requests',
    defaultScopes: ['repo', 'user', 'read:org'],
    redirectUri: `${API_URL}/api/v1/oauth/github/callback`,
    setupGuide: 'https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app',
    supportsOAuth: true,
    supportsApiToken: true,
    apiTokenDescription: 'Use GitHub Personal Access Token for direct API access'
  },
  {
    value: 'gitlab',
    label: 'GitLab',
    icon: <GitLabIcon />,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
    description: 'Access projects, issues, and merge requests',
    defaultScopes: ['api', 'read_user', 'read_repository', 'write_repository'],
    redirectUri: `${API_URL}/api/v1/oauth/gitlab/callback`,
    setupGuide: 'https://docs.gitlab.com/ee/integration/oauth_provider.html',
    supportsOAuth: true,
    supportsApiToken: true,
    apiTokenDescription: 'Use GitLab Personal Access Token for direct API access',
    supportsCustomBaseUrl: true,
  },
  {
    value: 'SLACK',
    label: 'Slack',
    icon: <SlackIcon />,
    color: 'text-[#E01E5A]',
    bgColor: 'bg-pink-50',
    description: 'Sync messages and files from channels',
    defaultScopes: [
      'channels:history',
      'channels:read',
      'groups:history',
      'groups:read',
      'im:history',
      'im:read',
      'mpim:history',
      'mpim:read',
      'users:read',
      'team:read',
    ],
    redirectUri: `${API_URL}/api/v1/oauth/slack/callback`,
    setupGuide: 'https://api.slack.com/apps',
    supportsOAuth: true,
    supportsApiToken: false
  },
  {
    value: 'gmail',
    label: 'Gmail',
    icon: <GmailIcon />,
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    description: 'Send, read, search, and manage emails',
    defaultScopes: [
      'https://www.googleapis.com/auth/gmail.modify',
      'https://www.googleapis.com/auth/gmail.send',
      'https://www.googleapis.com/auth/gmail.readonly',
      'https://www.googleapis.com/auth/userinfo.email',
    ],
    redirectUri: `${API_URL}/api/v1/oauth/gmail/callback`,
    setupGuide: 'https://console.cloud.google.com',
    supportsOAuth: true,
    supportsApiToken: false
  },
  {
    value: 'zoom',
    label: 'Zoom',
    icon: <ZoomIcon />,
    color: 'text-[#2D8CFF]',
    bgColor: 'bg-blue-50',
    description: 'Create and manage Zoom meetings',
    defaultScopes: [
      'meeting:write',
      'meeting:read',
      'recording:read',
      'user:read',
    ],
    redirectUri: `${API_URL}/api/v1/oauth/zoom/callback`,
    setupGuide: 'https://marketplace.zoom.us/',
    supportsOAuth: true,
    supportsApiToken: false
  },
  {
    value: 'google_calendar',
    label: 'Google Calendar',
    icon: <GoogleCalendarIcon />,
    color: 'text-[#4285F4]',
    bgColor: 'bg-blue-50',
    description: 'Manage calendar events and meetings',
    defaultScopes: [
      'https://www.googleapis.com/auth/calendar',
      'https://www.googleapis.com/auth/calendar.events',
      'https://www.googleapis.com/auth/userinfo.email',
    ],
    redirectUri: `${API_URL}/api/v1/oauth/google_calendar/callback`,
    setupGuide: 'https://console.cloud.google.com',
    supportsOAuth: true,
    supportsApiToken: false
  },
  {
    value: 'google_drive',
    label: 'Google Drive',
    icon: <GoogleDriveIcon />,
    color: 'text-[#4285F4]',
    bgColor: 'bg-green-50',
    description: 'Manage Drive files, Docs, and Sheets',
    defaultScopes: [
      'https://www.googleapis.com/auth/drive.file',
      'https://www.googleapis.com/auth/documents',
      'https://www.googleapis.com/auth/spreadsheets',
      'https://www.googleapis.com/auth/userinfo.email',
    ],
    redirectUri: `${API_URL}/api/v1/oauth/google_drive/callback`,
    setupGuide: 'https://console.cloud.google.com',
    supportsOAuth: true,
    supportsApiToken: false
  },
  {
    value: 'clickup',
    label: 'ClickUp',
    icon: <ClickUpIcon />,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
    description: 'Manage tasks, search issues, and add comments',
    defaultScopes: [],
    redirectUri: `${API_URL}/api/v1/oauth/clickup/callback`,
    setupGuide: 'https://clickup.com/api/developer-portal/authentication#oauth-flow',
    supportsOAuth: true,
    supportsApiToken: true,
    apiTokenDescription: 'Use ClickUp API Token for accessing tasks and workspaces'
  },
  {
    value: 'jira',
    label: 'Jira',
    icon: <JiraIcon />,
    color: 'text-[#2684FF]',
    bgColor: 'bg-blue-50',
    description: 'Manage issues, search JQL, and add comments',
    defaultScopes: ['read:me', 'read:jira-work', 'read:jira-user', 'write:jira-work', 'offline_access'],
    redirectUri: `${API_URL}/api/v1/oauth/jira/callback`,
    setupGuide: 'https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/',
    supportsOAuth: true,
    supportsApiToken: true,
    apiTokenDescription: 'Use Jira API Token with email and base URL for accessing issues'
  },
  {
    value: 'TELEGRAM',
    label: 'Telegram',
    icon: <TelegramIcon />,
    color: 'text-[#0088cc]',
    bgColor: 'bg-sky-50',
    description: 'Sync messages from Telegram chats and channels',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://core.telegram.org/bots#botfather',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Use Bot Token from BotFather to access Telegram messages'
  },
  {
    value: 'onepassword',
    label: '1Password',
    icon: <OnePasswordIcon />,
    color: 'text-[#0094F5]',
    bgColor: 'bg-blue-50',
    description: 'Secure credential & secret management',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://developer.1password.com/docs/service-accounts/',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Use 1Password Service Account Token for accessing vaults and secrets'
  },
  {
    value: 'mailisk',
    label: 'Mailisk',
    icon: <MailiskIcon />,
    color: 'text-gray-900',
    bgColor: 'bg-orange-50',
    description: 'Disposable inboxes for automated signup, email OTP, and magic-link testing',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://docs.mailisk.com/',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Use your Mailisk API key together with a namespace for tenant-specific test inboxes'
  },
  {
    value: 'twitter',
    label: 'Twitter / X',
    icon: <TwitterIcon />,
    color: 'text-gray-900',
    bgColor: 'bg-gray-100',
    description: 'Posts, mentions, and social engagement',
    defaultScopes: ['tweet.read', 'tweet.write', 'users.read', 'follows.read', 'follows.write', 'like.read', 'like.write', 'bookmark.read', 'offline.access'],
    redirectUri: `${API_URL}/api/v1/oauth/twitter/callback`,
    setupGuide: 'https://developer.twitter.com/en/portal/dashboard',
    supportsOAuth: true,
    supportsApiToken: true,
    apiTokenDescription: 'Use Bearer Token from the Developer Portal'
  },
  {
    value: 'linkedin',
    label: 'LinkedIn',
    icon: <LinkedInIcon />,
    color: 'text-[#0A66C2]',
    bgColor: 'bg-blue-50',
    description: 'Professional networking and posts',
    defaultScopes: ['openid', 'profile', 'email', 'w_member_social', 'w_organization_social', 'r_organization_social'],
    redirectUri: `${API_URL}/api/v1/oauth/linkedin/callback`,
    setupGuide: 'https://www.linkedin.com/developers/apps',
    supportsOAuth: true,
    supportsApiToken: true,
    apiTokenDescription: 'Use Access Token from your LinkedIn app'
  },
  {
    value: 'recall',
    label: 'Recall.ai',
    icon: <RecallIcon />,
    color: 'text-indigo-600',
    bgColor: 'bg-indigo-50',
    description: 'Meeting bots for Zoom, Meet, Teams & Slack',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://www.recall.ai/dashboard',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Use Recall.ai API key from your dashboard'
  },
  {
    value: 'newsapi',
    label: 'NewsAPI',
    icon: (
      <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
        <rect width="24" height="24" rx="6" fill="#1A73E8"/>
        <path d="M5 7h14M5 10h10M5 13h12M5 16h8" stroke="white" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    description: 'Search news articles from 150,000+ sources worldwide',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://newsapi.org/register',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Use your NewsAPI key from newsapi.org to search news articles'
  },
  {
    value: 'youtube',
    label: 'YouTube',
    icon: (
      <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none">
        <rect width="24" height="24" rx="6" fill="#FF0000"/>
        <path d="M19.615 7.197A2.508 2.508 0 0017.85 5.42C16.346 5 12 5 12 5s-4.346 0-5.85.42a2.508 2.508 0 00-1.765 1.777C4 8.713 4 12 4 12s0 3.287.385 4.803a2.508 2.508 0 001.765 1.777C7.654 19 12 19 12 19s4.346 0 5.85-.42a2.508 2.508 0 001.765-1.777C20 15.287 20 12 20 12s0-3.287-.385-4.803zM10 15V9l5.2 3-5.2 3z" fill="white"/>
      </svg>
    ),
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    description: 'Search and discover recent YouTube videos using the YouTube Data API v3',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://console.cloud.google.com/apis/credentials',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Use a YouTube Data API v3 key from Google Cloud Console (APIs & Services → Credentials → Create API Key, then restrict to YouTube Data API v3)'
  },
  {
    value: 'micromobility',
    label: 'Micromobility',
    icon: <MicromobilityIcon />,
    color: 'text-emerald-700',
    bgColor: 'bg-emerald-50',
    description: 'Fleet management for scooters, bikes, and micromobility vehicles via Dashboard',
    defaultScopes: [],
    redirectUri: `${API_URL}/api/v1/oauth/micromobility/callback`,
    setupGuide: 'https://example.com',
    supportsOAuth: false,
    supportsApiToken: true,
    supportsBasicAuth: true,
    apiTokenDescription: 'Paste the JWT token obtained from the login endpoint',
  },
  {
    value: 'openweather',
    label: 'OpenWeather',
    icon: <OpenWeatherIcon />,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
    description: 'Weather forecasts and current conditions with demand impact scoring for any location',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://openweathermap.org/api',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Use your OpenWeather API key from openweathermap.org',
  },
  {
    value: 'predicthq',
    label: 'PredictHQ',
    icon: <PredictHQIcon />,
    color: 'text-indigo-600',
    bgColor: 'bg-indigo-50',
    description: 'Event intelligence — concerts, sports, conferences with attendance-based demand multipliers',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://www.predicthq.com/support/how-to-find-your-api-token',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Use your PredictHQ API token from the control center',
  },
  {
    value: 'ticketmaster',
    label: 'Ticketmaster',
    icon: <TicketmasterIcon />,
    color: 'text-blue-700',
    bgColor: 'bg-blue-50',
    description: 'Concerts, sports, and live events near any location for demand forecasting',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://developer.ticketmaster.com/products-and-docs/apis/getting-started/',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Use your Ticketmaster Consumer Key (API key) from developer.ticketmaster.com',
  },
  {
    value: 'mapbox',
    label: 'Mapbox',
    icon: <MapboxIcon />,
    color: 'text-gray-900',
    bgColor: 'bg-gray-100',
    description: 'Static maps with vehicle markers, route overlays, and turn-by-turn directions',
    defaultScopes: [],
    redirectUri: '',
    setupGuide: 'https://docs.mapbox.com/api/overview/#access-tokens-and-token-scopes',
    supportsOAuth: false,
    supportsApiToken: true,
    apiTokenDescription: 'Use a Mapbox public access token (pk.*) from your Mapbox account',
  },
]

const COMMON_TAGS = [
  'production',
  'staging',
  'development',
  'internal-tool',
  'customer-support',
  'marketing',
  'engineering',
  'data-analysis',
  'automation'
]

export default function CreateOAuthAppPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [formData, setFormData] = useState({
    provider: '',
    app_name: '',
    auth_method: 'oauth',
    client_id: '',
    client_secret: '',
    redirect_uri: '',
    scopes: [] as string[],
    api_token: '',
    is_default: true,
    description: '',
    tags: [] as string[],
    is_internal_tool: false,
    config: {} as Record<string, any>,
  })

  const selectedProvider = PROVIDERS.find(p => p.value === formData.provider)

  const handleProviderChange = (provider: string) => {
    const providerInfo = PROVIDERS.find(p => p.value === provider) as typeof PROVIDERS[0] & { supportsBasicAuth?: boolean }
    if (providerInfo) {
      let authMethod = 'api_token'
      if (providerInfo.supportsBasicAuth) {
        authMethod = 'basic_auth'
      } else if (providerInfo.supportsOAuth) {
        authMethod = 'oauth'
      }
      setFormData({
        ...formData,
        provider,
        app_name: `${providerInfo.label} Integration`,
        redirect_uri: providerInfo.redirectUri,
        scopes: providerInfo.defaultScopes,
        description: providerInfo.description,
        auth_method: authMethod,
        config: {},
      })
    }
  }

  const handleScopeChange = (scope: string, checked: boolean) => {
    if (checked) {
      setFormData({ ...formData, scopes: [...formData.scopes, scope] })
    } else {
      setFormData({ ...formData, scopes: formData.scopes.filter(s => s !== scope) })
    }
  }

  const handleTagChange = (tag: string, checked: boolean) => {
    if (checked) {
      setFormData({ ...formData, tags: [...formData.tags, tag] })
    } else {
      setFormData({ ...formData, tags: formData.tags.filter(t => t !== tag) })
    }
  }

  const handleCustomTagAdd = (customTag: string) => {
    if (customTag && !formData.tags.includes(customTag)) {
      setFormData({ ...formData, tags: [...formData.tags, customTag] })
    }
  }

  const [createdApp, setCreatedApp] = useState<any>(null)
  const [showSuccessModal, setShowSuccessModal] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const result = await apiClient.createOAuthApp(formData)
      setCreatedApp(result)
      
      // For OAuth method, show success modal with authorize option
      if (formData.auth_method === 'oauth') {
        setShowSuccessModal(true)
      } else {
        // For API token / basic_auth, redirect directly
        router.push('/oauth-apps')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleAuthorize = () => {
    if (!createdApp) return
    
    const redirectUrl = encodeURIComponent(window.location.origin + '/oauth-apps')
    const authUrl = `${API_URL}/api/v1/oauth/${formData.provider.toLowerCase()}/authorize?oauth_app_id=${createdApp.id}&redirect_url=${redirectUrl}`
    window.location.href = authUrl
  }

  return (
    <DashboardPageShell
      title="Connect Account"
      description="Connect your GitHub, Slack, or other accounts to enable integrations."
      icon={Plus}
      badge="OAuth Apps"
      backHref="/oauth-apps"
      backLabel="Back to Connected Accounts"
      maxWidthClassName="max-w-5xl"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'OAuth Apps', href: '/oauth-apps' },
        { label: 'Connect Account' },
      ]}
    >
      <div className="[&_input]:rounded-[1rem] [&_input]:border [&_input]:border-black/10 [&_input]:bg-[#fcfaf5] [&_input]:px-4 [&_input]:py-3 [&_input]:text-sm [&_input]:text-gray-900 [&_input]:placeholder-gray-400 [&_input]:focus:border-transparent [&_input]:focus:outline-none [&_input]:focus:ring-2 [&_input]:focus:ring-[#79dfbc] [&_input[type='checkbox']]:!h-4 [&_input[type='checkbox']]:!w-4 [&_input[type='checkbox']]:!rounded [&_input[type='checkbox']]:!border-gray-300 [&_input[type='checkbox']]:!bg-white [&_input[type='checkbox']]:!p-0 [&_input[type='checkbox']]:focus:!ring-[#79dfbc] [&_input[type='radio']]:!h-4 [&_input[type='radio']]:!w-4 [&_input[type='radio']]:!border-gray-300 [&_input[type='radio']]:!bg-white [&_input[type='radio']]:focus:!ring-[#79dfbc] [&_select]:rounded-[1rem] [&_select]:border [&_select]:border-black/10 [&_select]:bg-[#fcfaf5] [&_select]:px-4 [&_select]:py-3 [&_select]:text-sm [&_select]:text-gray-900 [&_select]:focus:border-transparent [&_select]:focus:outline-none [&_select]:focus:ring-2 [&_select]:focus:ring-[#79dfbc] [&_textarea]:rounded-[1rem] [&_textarea]:border [&_textarea]:border-black/10 [&_textarea]:bg-[#fcfaf5] [&_textarea]:px-4 [&_textarea]:py-3 [&_textarea]:text-sm [&_textarea]:text-gray-900 [&_textarea]:placeholder-gray-400 [&_textarea]:focus:border-transparent [&_textarea]:focus:outline-none [&_textarea]:focus:ring-2 [&_textarea]:focus:ring-[#79dfbc] [&_label]:font-semibold [&_label]:text-gray-700 [&_.bg-white.rounded-lg.shadow-sm.border.border-gray-200.p-5]:rounded-[1.9rem] [&_.bg-white.rounded-lg.shadow-sm.border.border-gray-200.p-5]:border-[#e5d9ca] [&_.bg-white.rounded-lg.shadow-sm.border.border-gray-200.p-5]:bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] [&_.bg-white.rounded-lg.shadow-sm.border.border-gray-200.p-5]:shadow-[0_24px_60px_-46px_rgba(73,45,23,0.3)]">

        {error && (
          <div className="mb-5">
            <ErrorAlert message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Provider Selection */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
            <h2 className="text-base font-semibold text-gray-900 mb-3">Select Provider</h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              {PROVIDERS.map((provider) => (
                <button
                  key={provider.value}
                  type="button"
                  onClick={() => handleProviderChange(provider.value)}
                  className={`p-4 rounded-xl border-2 transition-all text-left hover:shadow-md ${
                    formData.provider === provider.value
                      ? 'border-[#ff444f] bg-red-50 shadow-md'
                      : 'border-gray-200 hover:border-gray-300 bg-white'
                  }`}
                >
                  <div className={`w-12 h-12 ${provider.bgColor} rounded-lg flex items-center justify-center mb-3 ${provider.color}`}>
                    {provider.icon}
                  </div>
                  <div className="font-semibold text-gray-900 text-sm">{provider.label}</div>
                  <div className="text-xs text-gray-500 mt-1 line-clamp-2">{provider.description}</div>
                </button>
              ))}
            </div>
          </div>

          {formData.provider && (
            <>
              {/* Basic Information */}
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
                <h2 className="text-base font-semibold text-gray-900 mb-3">Connection Details</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Connection Name *
                    </label>
                    <input
                      type="text"
                      required
                      value={formData.app_name}
                      onChange={(e) => setFormData({ ...formData, app_name: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent"
                      placeholder="e.g., My Work GitHub, Personal Slack"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Description
                    </label>
                    <textarea
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent"
                      rows={2}
                      placeholder="Optional description for this OAuth app"
                    />
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_default"
                      checked={formData.is_default}
                      onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                      className="w-4 h-4 text-[#ff444f] border-gray-300 rounded focus:ring-[#ff444f]"
                    />
                    <label htmlFor="is_default" className="text-sm text-gray-700">
                      Set as default connection for this provider
                    </label>
                  </div>
                </div>
              </div>

              {/* Authentication Method Selection */}
              {(selectedProvider?.supportsApiToken || (selectedProvider as any)?.supportsBasicAuth) && (
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
                  <h2 className="text-base font-semibold text-gray-900 mb-3">Authentication Method</h2>
                  <p className="text-sm text-gray-600 mb-3">
                    Choose how to authenticate with {selectedProvider?.label}
                  </p>
                  <div className="space-y-2.5">
                    {selectedProvider?.supportsOAuth && (
                      <label className="flex items-start gap-2.5 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
                        <input
                          type="radio"
                          name="auth_method"
                          value="oauth"
                          checked={formData.auth_method === 'oauth'}
                          onChange={(e) => setFormData({ ...formData, auth_method: e.target.value })}
                          className="mt-0.5 w-4 h-4 text-[#ff444f] border-gray-300 focus:ring-[#ff444f]"
                        />
                        <div>
                          <div className="font-medium text-gray-900 text-sm">OAuth Flow</div>
                          <div className="text-xs text-gray-600">
                            Standard OAuth 2.0 flow with user authorization. Requires OAuth app setup.
                          </div>
                        </div>
                      </label>
                    )}
                    {(selectedProvider as any)?.supportsBasicAuth && (
                      <label className="flex items-start gap-2.5 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
                        <input
                          type="radio"
                          name="auth_method"
                          value="basic_auth"
                          checked={formData.auth_method === 'basic_auth'}
                          onChange={(e) => setFormData({ ...formData, auth_method: e.target.value })}
                          className="mt-0.5 w-4 h-4 text-[#ff444f] border-gray-300 focus:ring-[#ff444f]"
                        />
                        <div>
                          <div className="font-medium text-gray-900 text-sm">Username & Password</div>
                          <div className="text-xs text-gray-600">
                            Login with username and password to obtain a JWT token automatically. Token is refreshed when expired.
                          </div>
                        </div>
                      </label>
                    )}
                    {selectedProvider?.supportsApiToken && (
                      <label className="flex items-start gap-2.5 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
                        <input
                          type="radio"
                          name="auth_method"
                          value="api_token"
                          checked={formData.auth_method === 'api_token'}
                          onChange={(e) => setFormData({ ...formData, auth_method: e.target.value })}
                          className="mt-0.5 w-4 h-4 text-[#ff444f] border-gray-300 focus:ring-[#ff444f]"
                        />
                        <div>
                          <div className="font-medium text-gray-900 text-sm">API Token</div>
                          <div className="text-xs text-gray-600">
                            {selectedProvider.apiTokenDescription}
                          </div>
                        </div>
                      </label>
                    )}
                  </div>
                </div>
              )}

              {/* Authentication Credentials */}
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
                <h2 className="text-base font-semibold text-gray-900 mb-3">
                  {formData.auth_method === 'api_token' ? 'API Token' : formData.auth_method === 'basic_auth' ? 'Login Credentials' : 'OAuth Credentials'}
                </h2>
                
                {formData.auth_method === 'basic_auth' ? (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Base URL *
                      </label>
                      <input
                        type="url"
                        required
                        value={formData.config.base_url || ''}
                        onChange={(e) => setFormData({ ...formData, config: { ...formData.config, base_url: e.target.value } })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                        placeholder="https://api.your-oto-instance.com"
                      />
                      <p className="text-xs text-gray-500 mt-1">Base URL of your API (must be HTTPS)</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Login Endpoint *
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.config.login_endpoint || ''}
                        onChange={(e) => setFormData({ ...formData, config: { ...formData.config, login_endpoint: e.target.value } })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                        placeholder="/admin-login-jwt/"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Endpoint to POST username/password to receive a JWT token (e.g. <code className="bg-gray-100 px-1 rounded">/admin-login-jwt/</code>)
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Token Field in Response *
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.config.token_response_field || ''}
                        onChange={(e) => setFormData({ ...formData, config: { ...formData.config, token_response_field: e.target.value } })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                        placeholder="token"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        JSON field name in the login response that contains the JWT (e.g. <code className="bg-gray-100 px-1 rounded">token</code>)
                      </p>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">
                          Username Field Name
                        </label>
                        <input
                          type="text"
                          value={formData.config.login_username_field || ''}
                          onChange={(e) => setFormData({ ...formData, config: { ...formData.config, login_username_field: e.target.value } })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                          placeholder="username"
                        />
                        <p className="text-xs text-gray-500 mt-1">Login body key for username (default: <code className="bg-gray-100 px-1 rounded">username</code>)</p>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">
                          Password Field Name
                        </label>
                        <input
                          type="text"
                          value={formData.config.login_password_field || ''}
                          onChange={(e) => setFormData({ ...formData, config: { ...formData.config, login_password_field: e.target.value } })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                          placeholder="password"
                        />
                        <p className="text-xs text-gray-500 mt-1">Login body key for password (default: <code className="bg-gray-100 px-1 rounded">password</code>)</p>
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Username *
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.config.username || ''}
                        onChange={(e) => setFormData({ ...formData, config: { ...formData.config, username: e.target.value } })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent text-sm"
                        placeholder="admin@your-company.com"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Password *
                      </label>
                      <input
                        type="password"
                        required
                        value={formData.api_token}
                        onChange={(e) => setFormData({ ...formData, api_token: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                        placeholder="Enter your password"
                      />
                      <p className="text-xs text-gray-500 mt-1">Encrypted and stored securely. Used to obtain and refresh the JWT token.</p>
                    </div>
                  </div>
                ) : formData.auth_method === 'oauth' ? (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Client ID *
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.client_id}
                        onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                        placeholder="Enter your OAuth client ID"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Client Secret *
                      </label>
                      <input
                        type="password"
                        required
                        value={formData.client_secret}
                        onChange={(e) => setFormData({ ...formData, client_secret: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                        placeholder="Enter your OAuth client secret"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        This will be encrypted and stored securely
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Redirect URI *
                      </label>
                      <input
                        type="url"
                        required
                        value={formData.redirect_uri}
                        onChange={(e) => setFormData({ ...formData, redirect_uri: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        This must match the redirect URI configured in your {selectedProvider?.label} app
                      </p>
                    </div>

                    {/* GitLab self-hosted URL field for OAuth */}
                    {formData.provider === 'gitlab' && (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">
                          GitLab Instance URL (optional)
                        </label>
                        <input
                          type="url"
                          value={formData.config.base_url || ''}
                          onChange={(e) => setFormData({
                            ...formData,
                            config: { ...formData.config, base_url: e.target.value }
                          })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                          placeholder="https://gitlab.com (default)"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          Leave empty for gitlab.com, or enter your self-hosted GitLab URL
                        </p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* GitLab-specific fields */}
                    {formData.provider === 'gitlab' && (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">
                          GitLab Instance URL (optional)
                        </label>
                        <input
                          type="url"
                          value={formData.config.base_url || ''}
                          onChange={(e) => setFormData({
                            ...formData,
                            config: { ...formData.config, base_url: e.target.value }
                          })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                          placeholder="https://gitlab.com (default)"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          Leave empty for gitlab.com, or enter your self-hosted GitLab URL
                        </p>
                      </div>
                    )}

                    {/* Recall.ai-specific fields */}
                    {formData.provider === 'recall' && (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1.5">
                            Region *
                          </label>
                          <select
                            value={formData.config.region || 'us-east-1'}
                            onChange={(e) => setFormData({
                              ...formData,
                              config: { ...formData.config, region: e.target.value }
                            })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent text-sm"
                          >
                            <option value="us-east-1">US East (N. Virginia)</option>
                            <option value="us-west-2">US West (Oregon)</option>
                            <option value="eu-central-1">EU (Frankfurt)</option>
                            <option value="ap-northeast-1">Asia Pacific (Tokyo)</option>
                          </select>
                          <p className="text-xs text-gray-500 mt-1">
                            Select the region matching your Recall.ai account. Check your Recall.ai dashboard for your region.
                          </p>
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1.5">
                            Webhook Secret (optional)
                          </label>
                          <input
                            type="password"
                            value={formData.config.webhook_secret || ''}
                            onChange={(e) => setFormData({
                              ...formData,
                              config: { ...formData.config, webhook_secret: e.target.value }
                            })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                            placeholder="Enter your Recall.ai webhook secret"
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            Optional webhook secret for verifying webhook events from Recall.ai
                          </p>
                        </div>
                      </>
                    )}

                    {/* Jira-specific fields */}
                    {formData.provider === 'jira' && (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1.5">
                            Jira Base URL *
                          </label>
                          <input
                            type="url"
                            required
                            value={formData.config.base_url || ''}
                            onChange={(e) => setFormData({
                              ...formData,
                              config: { ...formData.config, base_url: e.target.value }
                            })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                            placeholder="https://your-domain.atlassian.net"
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            Your Jira instance URL (e.g., https://your-domain.atlassian.net)
                          </p>
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1.5">
                            Email Address *
                          </label>
                          <input
                            type="email"
                            required
                            value={formData.config.email || ''}
                            onChange={(e) => setFormData({
                              ...formData,
                              config: { ...formData.config, email: e.target.value }
                            })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent text-sm"
                            placeholder="your-email@example.com"
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            The email address associated with your Jira account
                          </p>
                        </div>
                      </>
                    )}

                    {/* Micromobility-specific fields */}
                    {formData.provider === 'micromobility' && (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1.5">
                            Base URL *
                          </label>
                          <input
                            type="url"
                            required
                            value={formData.config.base_url || ''}
                            onChange={(e) => setFormData({
                              ...formData,
                              config: { ...formData.config, base_url: e.target.value }
                            })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                            placeholder="https://api.your-oto-instance.com"
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            The base URL of your API (must be HTTPS)
                          </p>
                        </div>
                        {formData.auth_method === 'api_token' && (
                          <>
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                                API Key Header
                              </label>
                              <input
                                type="text"
                                value={formData.config.api_key_header || 'Authorization'}
                                onChange={(e) => setFormData({
                                  ...formData,
                                  config: { ...formData.config, api_key_header: e.target.value }
                                })}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                                placeholder="Authorization"
                              />
                              <p className="text-xs text-gray-500 mt-1">
                                HTTP header name to send the token in (default: Authorization)
                              </p>
                            </div>
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                                API Key Format
                              </label>
                              <input
                                type="text"
                                value={formData.config.api_key_format || 'Bearer {token}'}
                                onChange={(e) => setFormData({
                                  ...formData,
                                  config: { ...formData.config, api_key_format: e.target.value }
                                })}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                                placeholder="Bearer {token}"
                              />
                              <p className="text-xs text-gray-500 mt-1">
                                Format string for the token value. Use <code className="bg-gray-100 px-1 rounded">{'{token}'}</code> as the placeholder (default: Bearer {'{token}'})
                              </p>
                            </div>
                          </>
                        )}
                      </>
                    )}
                    
                    {/* OpenWeather-specific fields */}
                    {formData.provider === 'openweather' && (
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1.5">Units</label>
                          <select
                            value={formData.config.units || 'metric'}
                            onChange={(e) => setFormData({ ...formData, config: { ...formData.config, units: e.target.value } })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent text-sm"
                          >
                            <option value="metric">Metric (°C, m/s)</option>
                            <option value="imperial">Imperial (°F, mph)</option>
                            <option value="standard">Standard (K)</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1.5">API Version</label>
                          <select
                            value={formData.config.api_version || '3.0'}
                            onChange={(e) => setFormData({ ...formData, config: { ...formData.config, api_version: e.target.value } })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent text-sm"
                          >
                            <option value="3.0">One Call 3.0 (recommended)</option>
                            <option value="2.5">Free Tier 2.5</option>
                          </select>
                          <p className="text-xs text-gray-500 mt-1">3.0 requires a paid subscription; falls back to 2.5 automatically</p>
                        </div>
                      </div>
                    )}

                    {/* PredictHQ-specific fields */}
                    {formData.provider === 'predicthq' && (
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1.5">Max Radius (km)</label>
                          <input
                            type="number"
                            value={formData.config.max_radius_km || 10}
                            onChange={(e) => setFormData({ ...formData, config: { ...formData.config, max_radius_km: Number(e.target.value) } })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent text-sm"
                            min={1} max={50}
                          />
                          <p className="text-xs text-gray-500 mt-1">Default search radius for nearby events</p>
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1.5">Impact Weight</label>
                          <input
                            type="number"
                            step="0.05"
                            value={formData.config.impact_weight || 0.30}
                            onChange={(e) => setFormData({ ...formData, config: { ...formData.config, impact_weight: Number(e.target.value) } })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent text-sm"
                            min={0.05} max={1.0}
                          />
                          <p className="text-xs text-gray-500 mt-1">Demand multiplier scale factor (0.05–1.0)</p>
                        </div>
                      </div>
                    )}

                    {/* Ticketmaster-specific fields */}
                    {formData.provider === 'ticketmaster' && (
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1.5">Max Radius (km)</label>
                          <input
                            type="number"
                            value={formData.config.max_radius_km || 10}
                            onChange={(e) => setFormData({ ...formData, config: { ...formData.config, max_radius_km: Number(e.target.value) } })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent text-sm"
                            min={1} max={50}
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1.5">Impact Weight</label>
                          <input
                            type="number"
                            step="0.05"
                            value={formData.config.impact_weight || 0.30}
                            onChange={(e) => setFormData({ ...formData, config: { ...formData.config, impact_weight: Number(e.target.value) } })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent text-sm"
                            min={0.05} max={1.0}
                          />
                        </div>
                      </div>
                    )}

                    {/* Mapbox-specific fields */}
                    {formData.provider === 'mapbox' && (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">Default Map Style</label>
                        <select
                          value={formData.config.style || 'mapbox/streets-v12'}
                          onChange={(e) => setFormData({ ...formData, config: { ...formData.config, style: e.target.value } })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent text-sm"
                        >
                          <option value="mapbox/streets-v12">Streets (default)</option>
                          <option value="mapbox/satellite-v9">Satellite</option>
                          <option value="mapbox/satellite-streets-v12">Satellite + Streets</option>
                          <option value="mapbox/light-v11">Light</option>
                          <option value="mapbox/dark-v11">Dark</option>
                          <option value="mapbox/outdoors-v12">Outdoors</option>
                        </select>
                        <p className="text-xs text-gray-500 mt-1">Default basemap style for static map images</p>
                      </div>
                    )}

                    {formData.provider === 'mailisk' && (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1.5">
                            Mailisk Namespace *
                          </label>
                          <input
                            type="text"
                            required
                            value={formData.config.namespace || ''}
                            onChange={(e) => setFormData({
                              ...formData,
                              config: { ...formData.config, namespace: e.target.value.trim().toLowerCase() }
                            })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                            placeholder="your-team"
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            The tenant inbox namespace. The agent will generate addresses like <code className="bg-gray-100 px-1 rounded">run-123@your-team.mailisk.net</code>.
                          </p>
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1.5">
                            Mailisk API Base URL
                          </label>
                          <input
                            type="url"
                            value={formData.config.base_url || ''}
                            onChange={(e) => setFormData({
                              ...formData,
                              config: { ...formData.config, base_url: e.target.value }
                            })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                            placeholder="https://api.mailisk.com"
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            Optional override. Leave blank to use the default Mailisk API endpoint.
                          </p>
                        </div>
                      </>
                    )}

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        {selectedProvider?.label} API Token *
                      </label>
                      <input
                        type="password"
                        required
                        value={formData.api_token}
                        onChange={(e) => setFormData({ ...formData, api_token: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent font-mono text-sm"
                        placeholder={`Enter your ${selectedProvider?.label} API token`}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        This will be encrypted and stored securely.
                        {formData.provider === 'github' && ' For GitHub, use a Personal Access Token.'}
                        {formData.provider === 'gitlab' && ' For GitLab, use a Personal Access Token from User Settings > Access Tokens.'}
                        {formData.provider === 'jira' && ' Generate this from your Atlassian Account Settings.'}
                        {formData.provider === 'clickup' && ' Generate this from your ClickUp App Settings.'}
                        {formData.provider === 'twitter' && ' For Twitter, use your Bearer Token from the Developer Portal.'}
                        {formData.provider === 'linkedin' && ' For LinkedIn, use an Access Token from your app.'}
                        {formData.provider === 'onepassword' && ' For 1Password, use a Service Account Token.'}
                        {formData.provider === 'mailisk' && ' For Mailisk, use the API key from your Mailisk dashboard.'}
                        {formData.provider === 'recall' && ' For Recall.ai, use your API key from the Recall.ai dashboard.'}
                        {formData.provider === 'micromobility' && ' For Micromobility, use the JWT token returned by the admin login endpoint (POST /admin-login-jwt/).'}
                        {formData.provider === 'openweather' && ' Get your API key from openweathermap.org after signing up.'}
                        {formData.provider === 'predicthq' && ' Find your API token in the PredictHQ Control Center under API Credentials.'}
                        {formData.provider === 'ticketmaster' && ' Use the Consumer Key from your app at developer.ticketmaster.com.'}
                        {formData.provider === 'mapbox' && ' Use a public token (pk.*) from your Mapbox account tokens page.'}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Scopes */}
              {selectedProvider && selectedProvider.defaultScopes.length > 0 && formData.auth_method === 'oauth' && (
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
                  <h2 className="text-base font-semibold text-gray-900 mb-3">OAuth Scopes</h2>
                  <p className="text-sm text-gray-600 mb-3">
                    Select the permissions your app needs. These are the recommended scopes for {selectedProvider.label}.
                  </p>
                  <div className="space-y-2">
                    {selectedProvider.defaultScopes.map((scope) => (
                      <label key={scope} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={formData.scopes.includes(scope)}
                          onChange={(e) => handleScopeChange(scope, e.target.checked)}
                          className="w-4 h-4 text-[#ff444f] border-gray-300 rounded focus:ring-[#ff444f]"
                        />
                        <code className="text-xs bg-gray-100 px-2 py-0.5 rounded">{scope}</code>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Tags and Configuration */}
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
                <h2 className="text-base font-semibold text-gray-900 mb-3">Tags & Configuration</h2>
                
                <div className="space-y-5">
                  {/* Tags */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Tags
                    </label>
                    <p className="text-xs text-gray-600 mb-2.5">
                      Add tags to categorize and organize your OAuth integrations
                    </p>
                    
                    {/* Common Tags */}
                    <div className="flex flex-wrap gap-1.5 mb-2.5">
                      {COMMON_TAGS.map((tag) => (
                        <label key={tag} className="flex items-center">
                          <input
                            type="checkbox"
                            checked={formData.tags.includes(tag)}
                            onChange={(e) => handleTagChange(tag, e.target.checked)}
                            className="sr-only"
                          />
                          <span 
                            className={`px-2.5 py-1 text-xs rounded-full cursor-pointer transition-colors ${
                              formData.tags.includes(tag)
                                ? 'bg-red-100 text-red-800 border border-red-300'
                                : 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200'
                            }`}
                          >
                            {tag}
                          </span>
                        </label>
                      ))}
                    </div>

                    {/* Custom Tag Input */}
                    <div className="flex gap-2">
                      <input
                        type="text"
                        placeholder="Add custom tag..."
                        className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#ff444f] focus:border-transparent"
                        onKeyPress={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault()
                            const target = e.target as HTMLInputElement
                            handleCustomTagAdd(target.value.trim())
                            target.value = ''
                          }
                        }}
                      />
                      <button
                        type="button"
                        onClick={(e) => {
                          const input = (e.target as HTMLElement).previousElementSibling as HTMLInputElement
                          handleCustomTagAdd(input.value.trim())
                          input.value = ''
                        }}
                        className="px-4 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                      >
                        Add
                      </button>
                    </div>

                    {/* Selected Tags */}
                    {formData.tags.length > 0 && (
                      <div className="mt-2.5">
                        <p className="text-xs text-gray-600 mb-1.5">Selected tags:</p>
                        <div className="flex flex-wrap gap-1.5">
                          {formData.tags.map((tag) => (
                            <span
                              key={tag}
                              className="inline-flex items-center gap-1 px-2.5 py-0.5 text-xs bg-red-100 text-red-800 rounded-full"
                            >
                              {tag}
                              <button
                                type="button"
                                onClick={() => handleTagChange(tag, false)}
                                className="ml-0.5 text-[#ff444f] hover:text-red-800"
                              >
                                ×
                              </button>
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Internal Tool Flag */}
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_internal_tool"
                      checked={formData.is_internal_tool}
                      onChange={(e) => setFormData({ ...formData, is_internal_tool: e.target.checked })}
                      className="w-4 h-4 text-[#ff444f] border-gray-300 rounded focus:ring-[#ff444f]"
                    />
                    <div>
                      <label htmlFor="is_internal_tool" className="text-sm font-medium text-gray-700">
                        Mark as Internal Tool Integration
                      </label>
                      <p className="text-xs text-gray-500">
                        This helps identify OAuth integrations used by custom internal tools
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Setup Guide */}
              {selectedProvider && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <svg className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                    </svg>
                    <div>
                      <h3 className="text-sm font-medium text-amber-900 mb-1.5">Need Help?</h3>
                      <p className="text-sm text-amber-800 mb-2.5">
                        To get your Client ID and Client Secret, you need to create an OAuth app in {selectedProvider.label}.
                      </p>
                      <a
                        href={selectedProvider.setupGuide}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-amber-700 hover:text-amber-800 font-medium underline"
                      >
                        View {selectedProvider.label} Setup Guide →
                      </a>
                    </div>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3">
                <button
                  type="submit"
                  disabled={loading}
                  className="flex-1 px-5 py-2.5 bg-gradient-to-r from-[#ff444f] to-red-600 hover:from-red-600 hover:to-red-700 text-white rounded-lg transition-all shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <LoadingSpinner size="sm" />
                      Connecting...
                    </span>
                  ) : (
                    'Connect Account'
                  )}
                </button>
                <Link
                  href="/oauth-apps"
                  className="px-5 py-2.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium text-center text-sm"
                >
                  Cancel
                </Link>
              </div>
            </>
          )}
        </form>

        {/* Success Modal */}
        {showSuccessModal && createdApp && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
            <div className="w-full max-w-md rounded-[1.9rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] p-6 shadow-[0_32px_90px_-42px_rgba(73,45,23,0.35)]">
              <div className="text-center mb-5">
                <div className="mx-auto w-14 h-14 bg-emerald-100 rounded-full flex items-center justify-center mb-3">
                  <svg className="w-7 h-7 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h2 className="text-xl font-bold text-gray-900 mb-2">Connection Created!</h2>
                <p className="text-sm text-gray-600">
                  Your {selectedProvider?.label} connection has been created successfully.
                </p>
              </div>

              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3.5 mb-5">
                <div className="flex gap-2">
                  <svg className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <div className="flex-1">
                    <h3 className="text-sm font-medium text-yellow-900 mb-1">Authorization Required</h3>
                    <p className="text-xs text-yellow-800">
                      To complete the setup, you need to authorize this app with your {selectedProvider?.label} account.
                    </p>
                  </div>
                </div>
              </div>

              <div className="space-y-2.5">
                <button
                  onClick={handleAuthorize}
                  className="w-full px-5 py-2.5 bg-gradient-to-r from-[#ff444f] to-red-600 hover:from-red-600 hover:to-red-700 text-white rounded-lg transition-all shadow-sm hover:shadow-md font-medium text-sm flex items-center justify-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Authorize with {selectedProvider?.label}
                </button>
                <button
                  onClick={() => router.push('/oauth-apps')}
                  className="w-full px-5 py-2.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium text-sm"
                >
                  Skip for Now
                </button>
              </div>

              <p className="text-xs text-gray-500 text-center mt-3">
                You can authorize later from the Connected Accounts page
              </p>
            </div>
          </div>
        )}
      </div>
    </DashboardPageShell>
  )
}
