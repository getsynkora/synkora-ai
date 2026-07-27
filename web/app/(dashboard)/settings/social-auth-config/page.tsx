'use client'

import { useState, useEffect } from 'react'
import { Lock, Plus, ShieldCheck, X, Edit2, Power, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import { socialAuthConfigApi, type ProviderConfig } from '@/lib/api/social-auth-config'
import { platformOAuthAppsApi, type PlatformOAuthApp } from '@/lib/api/platform-oauth-apps'
import { extractErrorMessage } from '@/lib/api/error'
import type { SocialProvider } from '@/types/social-auth'
import { usePermissions } from '@/hooks/usePermissions'
import { ProviderIcon } from '@/components/social-auth/ProviderIcon'
import DashboardPageShell, { DashboardPagePanel, DashboardPageTabs } from '@/components/dashboard/DashboardPageShell'

type ActiveTab = 'login-providers' | 'platform-oauth-apps'

const API_URL = process.env.NEXT_PUBLIC_API_URL || ''

const LOGIN_PROVIDER_CALLBACK: Record<string, string> = {
  google:    '/api/v1/auth/google/callback',
  microsoft: '/api/v1/auth/microsoft/callback',
  apple:     '/api/v1/auth/apple/callback',
}

const PLATFORM_PROVIDER_CALLBACK: Record<string, string> = {
  gmail:           '/api/v1/oauth/gmail/callback',
  google_calendar: '/api/v1/oauth/google_calendar/callback',
  google_drive:    '/api/v1/oauth/google_drive/callback',
  slack:           '/api/v1/oauth/slack/callback',
  github:          '/api/v1/oauth/github/callback',
  gitlab:          '/api/v1/oauth/gitlab/callback',
  jira:            '/api/v1/oauth/jira/callback',
  zoom:            '/api/v1/oauth/zoom/callback',
  clickup:         '/api/v1/oauth/clickup/callback',
  twitter:         '/api/v1/oauth/twitter/callback',
  linkedin:        '/api/v1/oauth/linkedin/callback',
  zendesk:         '/api/v1/oauth/zendesk/callback',
  zoho_crm:        '/api/v1/oauth/zoho/callback',
  hubspot:         '/api/v1/oauth/hubspot/callback',
  intercom:        '/api/v1/oauth/intercom/callback',
  salesforce:      '/api/v1/oauth/salesforce/callback',
}

function redirectUriFor(provider: string, type: 'login' | 'platform'): string {
  const path = type === 'login' ? LOGIN_PROVIDER_CALLBACK[provider] : PLATFORM_PROVIDER_CALLBACK[provider]
  return path ? `${API_URL}${path}` : ''
}

interface EditFormData {
  client_id: string
  client_secret: string
  redirect_uri: string
}

interface PlatformOAuthAppFormData {
  provider: string
  app_name: string
  auth_method: string
  client_id: string
  client_secret: string
  redirect_uri: string
  scopes: string[]
  description: string
}

const PROVIDER_INFO: Record<SocialProvider, { name: string; description: string }> = {
  google:    { name: 'Google',    description: 'Allow users to sign in with their Google account' },
  microsoft: { name: 'Microsoft', description: 'Allow users to sign in with their Microsoft account' },
  apple:     { name: 'Apple',     description: 'Allow users to sign in with their Apple ID' },
}

const PLATFORM_PROVIDERS = [
  'gmail', 'google_calendar', 'google_drive', 'slack', 'github', 'gitlab',
  'jira', 'zoom', 'clickup', 'twitter', 'linkedin', 'zendesk',
  'zoho_crm', 'hubspot', 'intercom', 'salesforce',
] as const
type PlatformProvider = typeof PLATFORM_PROVIDERS[number]

const PLATFORM_PROVIDER_INFO: Record<PlatformProvider, {
  name: string; description: string; initials: string; bg: string; text: string; defaultScopes: string[]
}> = {
  gmail:           { name: 'Gmail',           description: 'Read and send emails via Gmail',                  initials: 'GM', bg: 'bg-red-100',    text: 'text-red-700',    defaultScopes: ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/userinfo.email'] },
  google_calendar: { name: 'Google Calendar', description: 'Manage calendar events and schedules',             initials: 'GC', bg: 'bg-blue-100',   text: 'text-blue-700',   defaultScopes: ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events', 'https://www.googleapis.com/auth/userinfo.email'] },
  google_drive:    { name: 'Google Drive',    description: 'Access and manage Drive files',                    initials: 'GD', bg: 'bg-yellow-100', text: 'text-yellow-700', defaultScopes: ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/documents', 'https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/userinfo.email'] },
  slack:           { name: 'Slack',           description: 'Send messages and interact with Slack workspaces', initials: 'SL', bg: 'bg-purple-100', text: 'text-purple-700', defaultScopes: ['channels:history', 'channels:read', 'groups:history', 'groups:read', 'im:history', 'im:read', 'users:read', 'team:read'] },
  github:          { name: 'GitHub',          description: 'Access repositories, issues, and pull requests',   initials: 'GH', bg: 'bg-gray-100',   text: 'text-gray-700',   defaultScopes: ['repo', 'user', 'read:org'] },
  gitlab:          { name: 'GitLab',          description: 'Access GitLab projects and merge requests',        initials: 'GL', bg: 'bg-orange-100', text: 'text-orange-700', defaultScopes: ['api', 'read_user', 'read_repository', 'write_repository'] },
  jira:            { name: 'Jira',            description: 'Manage Jira issues and projects',                  initials: 'JR', bg: 'bg-blue-100',   text: 'text-blue-700',   defaultScopes: ['read:me', 'read:jira-work', 'read:jira-user', 'write:jira-work', 'read:board-scope:jira-software', 'read:sprint:jira-software', 'write:sprint:jira-software', 'offline_access'] },
  zoom:            { name: 'Zoom',            description: 'Create and manage Zoom meetings',                  initials: 'ZM', bg: 'bg-sky-100',    text: 'text-sky-700',    defaultScopes: ['meeting:write', 'meeting:read', 'recording:read', 'user:read'] },
  clickup:         { name: 'ClickUp',         description: 'Manage tasks and workspaces in ClickUp',           initials: 'CU', bg: 'bg-pink-100',   text: 'text-pink-700',   defaultScopes: [] },
  twitter:         { name: 'Twitter / X',     description: 'Post tweets and access Twitter data',              initials: 'TW', bg: 'bg-sky-100',    text: 'text-sky-700',    defaultScopes: ['tweet.read', 'tweet.write', 'users.read', 'offline.access'] },
  linkedin:        { name: 'LinkedIn',        description: 'Post content and access LinkedIn data',            initials: 'LI', bg: 'bg-blue-100',   text: 'text-blue-700',   defaultScopes: ['openid', 'profile', 'email', 'w_member_social'] },
  zendesk:         { name: 'Zendesk',         description: 'Manage support tickets in Zendesk',                initials: 'ZD', bg: 'bg-green-100',  text: 'text-green-700',  defaultScopes: ['read', 'write'] },
  zoho_crm:        { name: 'Zoho CRM',        description: 'Access and update Zoho CRM records',               initials: 'ZC', bg: 'bg-red-100',    text: 'text-red-700',    defaultScopes: ['ZohoCRM.modules.ALL', 'ZohoCRM.settings.ALL', 'ZohoCRM.users.READ', 'ZohoCRM.org.READ', 'offline_access'] },
  hubspot:         { name: 'HubSpot',         description: 'Manage HubSpot contacts and deals',                initials: 'HS', bg: 'bg-orange-100', text: 'text-orange-700', defaultScopes: ['crm.objects.contacts.read', 'crm.objects.contacts.write', 'crm.objects.deals.read'] },
  intercom:        { name: 'Intercom',        description: 'Access Intercom conversations and contacts',       initials: 'IC', bg: 'bg-blue-100',   text: 'text-blue-700',   defaultScopes: [] },
  salesforce:      { name: 'Salesforce',      description: 'Access Salesforce CRM data and records',           initials: 'SF', bg: 'bg-sky-100',    text: 'text-sky-700',    defaultScopes: ['api', 'refresh_token', 'offline_access'] },
}

const EMPTY_PLATFORM_FORM: PlatformOAuthAppFormData = {
  provider: '', app_name: '', auth_method: 'oauth', client_id: '', client_secret: '', redirect_uri: '', scopes: [], description: '',
}

// Input/label styles matching oauth-apps/create
const inputCls = 'w-full rounded-[1rem] border border-black/10 bg-[#fcfaf5] px-4 py-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]'
const selectCls = 'w-full rounded-[1rem] border border-black/10 bg-[#fcfaf5] px-4 py-3 text-sm text-gray-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]'
const labelCls = 'mb-1.5 block text-sm font-semibold text-gray-700'
const sectionCls = 'rounded-[1.25rem] border border-[#e5d9ca] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(249,245,239,0.96))] p-5 shadow-[0_24px_60px_-46px_rgba(73,45,23,0.3)]'

function ProviderAvatar({ provider }: { provider: string }) {
  const info = PLATFORM_PROVIDER_INFO[provider as PlatformProvider]
  return (
    <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl text-xs font-bold ${info?.bg ?? 'bg-gray-100'} ${info?.text ?? 'text-gray-700'}`}>
      {info?.initials ?? provider.slice(0, 2).toUpperCase()}
    </div>
  )
}

function ScopesField({
  scopes,
  defaultScopes,
  onChange,
}: {
  scopes: string[]
  defaultScopes: string[]
  onChange: (s: string[]) => void
}) {
  const [custom, setCustom] = useState('')

  const toggle = (scope: string, checked: boolean) => {
    onChange(checked ? [...scopes, scope] : scopes.filter(s => s !== scope))
  }

  const addCustom = () => {
    const trimmed = custom.trim()
    if (trimmed && !scopes.includes(trimmed)) {
      onChange([...scopes, trimmed])
    }
    setCustom('')
  }

  const allScopes = Array.from(new Set([...defaultScopes, ...scopes]))

  return (
    <div className="space-y-2">
      {allScopes.length > 0 ? (
        <div className="max-h-40 overflow-y-auto space-y-1.5 rounded-[1rem] border border-black/10 bg-[#fcfaf5] p-3">
          {allScopes.map(scope => (
            <label key={scope} className="flex items-center gap-2.5 cursor-pointer group">
              <input
                type="checkbox"
                checked={scopes.includes(scope)}
                onChange={e => toggle(scope, e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-[#10717C] focus:ring-[#79dfbc]"
              />
              <span className="text-xs font-mono text-gray-700 group-hover:text-gray-900 break-all">{scope}</span>
            </label>
          ))}
        </div>
      ) : null}
      <div className="flex gap-2">
        <input
          type="text"
          value={custom}
          onChange={e => setCustom(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCustom() } }}
          className={`${inputCls} flex-1`}
          placeholder="Add custom scope and press Enter"
        />
        <button
          type="button"
          onClick={addCustom}
          className="rounded-[1rem] border border-black/10 bg-[#fcfaf5] px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-[#f0ece3] transition-colors"
        >
          Add
        </button>
      </div>
    </div>
  )
}

export default function SocialAuthConfigPage() {
  const { hasPermission, loading: permissionsLoading } = usePermissions()
  const [activeTab, setActiveTab] = useState<ActiveTab>('login-providers')

  // ── Login Providers ───────────────────────────────────────────────────────
  const [providers, setProviders] = useState<ProviderConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [deleteConfirm, setDeleteConfirm] = useState<SocialProvider | null>(null)
  const [editingProvider, setEditingProvider] = useState<SocialProvider | null>(null)
  const [creatingProvider, setCreatingProvider] = useState<SocialProvider | null>(null)
  const [editFormData, setEditFormData] = useState<EditFormData>({ client_id: '', client_secret: '', redirect_uri: '' })
  const [createFormData, setCreateFormData] = useState<EditFormData>({ client_id: '', client_secret: '', redirect_uri: '' })
  const [saving, setSaving] = useState(false)

  // ── Platform OAuth Apps ───────────────────────────────────────────────────
  const [platformApps, setPlatformApps] = useState<PlatformOAuthApp[]>([])
  const [platformLoading, setPlatformLoading] = useState(false)
  const [platformDeleteConfirm, setPlatformDeleteConfirm] = useState<number | null>(null)
  const [platformEditingApp, setPlatformEditingApp] = useState<PlatformOAuthApp | null>(null)
  const [platformCreating, setPlatformCreating] = useState(false)
  const [platformCreateForm, setPlatformCreateForm] = useState<PlatformOAuthAppFormData>(EMPTY_PLATFORM_FORM)
  const [platformEditForm, setPlatformEditForm] = useState<PlatformOAuthAppFormData>(EMPTY_PLATFORM_FORM)
  const [platformSaving, setPlatformSaving] = useState(false)

  useEffect(() => { fetchProviders() }, [])
  useEffect(() => {
    if (activeTab === 'platform-oauth-apps' && platformApps.length === 0 && !platformLoading) {
      fetchPlatformApps()
    }
  }, [activeTab])

  // ── Handlers: Login Providers ─────────────────────────────────────────────
  const fetchProviders = async () => {
    try {
      setLoading(true)
      setProviders(await socialAuthConfigApi.listProviderConfigs().then(d => Array.isArray(d) ? d : []))
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to load providers'))
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (provider: SocialProvider) => {
    try {
      await socialAuthConfigApi.deleteProviderConfig(provider)
      await fetchProviders()
      setDeleteConfirm(null)
      toast.success('Provider deleted')
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to delete provider'))
    }
  }

  const handleToggleEnabled = async (provider: ProviderConfig) => {
    try {
      await socialAuthConfigApi.updateProviderConfig(provider.provider_name as SocialProvider, {
        provider: provider.provider_name as SocialProvider,
        client_id: provider.client_id,
        redirect_uri: provider.redirect_uri,
        is_enabled: !provider.enabled,
      })
      await fetchProviders()
      toast.success(`Provider ${!provider.enabled ? 'enabled' : 'disabled'}`)
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to toggle provider'))
    }
  }

  const handleEdit = (provider: ProviderConfig) => {
    setEditingProvider(provider.provider_name as SocialProvider)
    setEditFormData({
      client_id: provider.client_id || '',
      client_secret: '',
      redirect_uri: provider.redirect_uri || redirectUriFor(provider.provider_name, 'login'),
    })
  }

  const handleSaveEdit = async () => {
    if (!editingProvider) return
    try {
      setSaving(true)
      await socialAuthConfigApi.updateProviderConfig(editingProvider, {
        provider: editingProvider,
        client_id: editFormData.client_id,
        client_secret: editFormData.client_secret,
        redirect_uri: editFormData.redirect_uri,
        is_enabled: providers.find(p => p.provider_name === editingProvider)?.enabled || false,
      })
      await fetchProviders()
      setEditingProvider(null)
      toast.success('Provider updated')
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to update provider'))
    } finally {
      setSaving(false)
    }
  }

  const handleCreate = async () => {
    if (!creatingProvider) return
    try {
      setSaving(true)
      await socialAuthConfigApi.createProviderConfig({
        provider: creatingProvider,
        client_id: createFormData.client_id,
        client_secret: createFormData.client_secret,
        redirect_uri: createFormData.redirect_uri,
        is_enabled: true,
      })
      await fetchProviders()
      setCreatingProvider(null)
      toast.success('Provider created')
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to create provider'))
    } finally {
      setSaving(false)
    }
  }

  // ── Handlers: Platform OAuth Apps ─────────────────────────────────────────
  const fetchPlatformApps = async () => {
    try {
      setPlatformLoading(true)
      setPlatformApps(await platformOAuthAppsApi.list())
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to load platform OAuth apps'))
    } finally {
      setPlatformLoading(false)
    }
  }

  const openPlatformCreate = (provider?: PlatformProvider) => {
    const info = provider ? PLATFORM_PROVIDER_INFO[provider] : null
    setPlatformCreateForm({
      provider: provider ?? '',
      app_name: info ? `${info.name} Integration` : '',
      auth_method: 'oauth',
      client_id: '',
      client_secret: '',
      redirect_uri: provider ? redirectUriFor(provider, 'platform') : '',
      scopes: info?.defaultScopes ?? [],
      description: info?.description ?? '',
    })
    setPlatformCreating(true)
  }

  const handlePlatformProviderChange = (provider: string) => {
    const info = PLATFORM_PROVIDER_INFO[provider as PlatformProvider]
    setPlatformCreateForm(f => ({
      ...f,
      provider,
      app_name: info ? `${info.name} Integration` : f.app_name,
      redirect_uri: redirectUriFor(provider, 'platform'),
      scopes: info?.defaultScopes ?? [],
      description: info?.description ?? '',
    }))
  }

  const handlePlatformCreate = async () => {
    try {
      setPlatformSaving(true)
      const isGitHubApp = platformCreateForm.auth_method === 'github_app'
      await platformOAuthAppsApi.create({
        provider: platformCreateForm.provider,
        app_name: platformCreateForm.app_name,
        auth_method: platformCreateForm.auth_method,
        client_id: platformCreateForm.client_id,
        client_secret: platformCreateForm.client_secret,
        redirect_uri: isGitHubApp ? undefined : platformCreateForm.redirect_uri,
        scopes: isGitHubApp ? undefined : platformCreateForm.scopes,
        description: platformCreateForm.description || undefined,
      })
      await fetchPlatformApps()
      setPlatformCreating(false)
      toast.success('Platform OAuth app created')
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to create platform OAuth app'))
    } finally {
      setPlatformSaving(false)
    }
  }

  const handlePlatformSaveEdit = async () => {
    if (!platformEditingApp) return
    try {
      setPlatformSaving(true)
      const isGitHubApp = platformEditForm.auth_method === 'github_app'
      await platformOAuthAppsApi.update(platformEditingApp.id, {
        app_name: platformEditForm.app_name,
        client_id: platformEditForm.client_id,
        client_secret: platformEditForm.client_secret || undefined,
        redirect_uri: isGitHubApp ? undefined : platformEditForm.redirect_uri,
        scopes: isGitHubApp ? undefined : platformEditForm.scopes,
        description: platformEditForm.description || undefined,
      })
      await fetchPlatformApps()
      setPlatformEditingApp(null)
      toast.success('Platform OAuth app updated')
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to update platform OAuth app'))
    } finally {
      setPlatformSaving(false)
    }
  }

  const handlePlatformToggle = async (app: PlatformOAuthApp) => {
    try {
      await platformOAuthAppsApi.toggle(app.id)
      await fetchPlatformApps()
      toast.success(`${app.app_name} ${app.is_active ? 'disabled' : 'enabled'}`)
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to toggle app'))
    }
  }

  const handlePlatformDelete = async (id: number) => {
    try {
      await platformOAuthAppsApi.remove(id)
      await fetchPlatformApps()
      setPlatformDeleteConfirm(null)
      toast.success('Platform OAuth app deleted')
    } catch (err: any) {
      toast.error(extractErrorMessage(err, 'Failed to delete app'))
    }
  }

  // ── Derived ───────────────────────────────────────────────────────────────
  const configuredProviderNames = providers.map(p => p.provider_name)
  const availableLoginProviders = (Object.keys(PROVIDER_INFO) as SocialProvider[]).filter(
    p => !configuredProviderNames.includes(p)
  )
  const configuredPlatformProviders = platformApps.map(a => a.provider)
  const availablePlatformProviders = PLATFORM_PROVIDERS.filter(p => !configuredPlatformProviders.includes(p))

  const isPlatformOwner = hasPermission('platform', 'read')

  if (loading || permissionsLoading) {
    return <div className="flex min-h-screen items-center justify-center"><LoadingSpinner size="lg" /></div>
  }

  if (!isPlatformOwner) {
    return (
      <DashboardPageShell title="Social Authentication" description="Configure OAuth providers." icon={ShieldCheck} badge="Settings" backHref="/settings/profile" backLabel="Back to Settings" breadcrumbs={[{ label: 'Home', href: '/' }, { label: 'Settings', href: '/settings/profile' }, { label: 'Social Auth' }]}>
        <DashboardPagePanel className="p-10 text-center">
          <Lock className="mx-auto mb-4 h-12 w-12 text-[#9a7a5e]" />
          <h3 className="text-lg font-semibold text-gray-900">Access Denied</h3>
          <p className="mt-2 text-sm text-gray-600">This page is only accessible to platform owners.</p>
        </DashboardPagePanel>
      </DashboardPageShell>
    )
  }

  return (
    <>
      <DashboardPageShell
        title="Social Authentication"
        description="Configure OAuth providers for user authentication and platform integrations."
        icon={ShieldCheck}
        badge="Settings"
        backHref="/settings/profile"
        backLabel="Back to Settings"
        breadcrumbs={[{ label: 'Home', href: '/' }, { label: 'Settings', href: '/settings/profile' }, { label: 'Social Auth' }]}
        stats={[
          { label: 'Configured', value: activeTab === 'login-providers' ? providers.length : platformApps.length },
          { label: 'Enabled', value: activeTab === 'login-providers' ? providers.filter(p => p.enabled).length : platformApps.filter(a => a.is_active).length },
        ]}
        actions={
          activeTab === 'platform-oauth-apps' ? (
            <button onClick={() => openPlatformCreate()} className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black">
              <Plus size={16} />Add OAuth App
            </button>
          ) : null
        }
      >
        <div className="space-y-5">
          <DashboardPageTabs
            activeId={activeTab}
            onChange={id => setActiveTab(id as ActiveTab)}
            items={[
              { id: 'login-providers', label: 'Login Providers' },
              { id: 'platform-oauth-apps', label: 'Platform OAuth Apps' },
            ]}
          />

          {/* ── LOGIN PROVIDERS ──────────────────────────────────────────── */}
          {activeTab === 'login-providers' && (
            <div className="space-y-4">
              {providers.length > 0 && (
                <div className="space-y-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Configured Providers</p>
                  {providers.map(provider => {
                    const info = PROVIDER_INFO[provider.provider_name as SocialProvider]
                    return (
                      <DashboardPagePanel key={provider.id} className="overflow-hidden">
                        <div className="flex items-center gap-4 p-4">
                          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl border border-gray-100 bg-white shadow-sm">
                            <ProviderIcon provider={provider.provider_name as SocialProvider} size="sm" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-semibold text-gray-900">{info?.name ?? provider.provider_name}</span>
                              <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${provider.enabled ? 'bg-[#ebf5ee] text-[#24543b]' : 'bg-gray-100 text-gray-500'}`}>
                                <span className={`h-1.5 w-1.5 rounded-full ${provider.enabled ? 'bg-[#24543b]' : 'bg-gray-400'}`} />
                                {provider.enabled ? 'Enabled' : 'Disabled'}
                              </span>
                            </div>
                            <p className="mt-0.5 text-xs text-gray-500 truncate">Client ID: <code className="font-mono">{provider.client_id?.slice(0, 24)}…</code></p>
                          </div>
                          <div className="flex items-center gap-1">
                            <button onClick={() => handleEdit(provider)} className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700" title="Edit"><Edit2 size={15} /></button>
                            <button onClick={() => handleToggleEnabled(provider)} className={`rounded-lg p-2 transition-colors ${provider.enabled ? 'text-gray-400 hover:bg-gray-100 hover:text-gray-700' : 'text-emerald-600 hover:bg-emerald-50'}`} title={provider.enabled ? 'Disable' : 'Enable'}><Power size={15} /></button>
                            {deleteConfirm === provider.provider_name ? (
                              <div className="flex items-center gap-1.5 ml-1">
                                <button onClick={() => handleDelete(provider.provider_name as SocialProvider)} className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700 transition-colors">Confirm</button>
                                <button onClick={() => setDeleteConfirm(null)} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50 transition-colors">Cancel</button>
                              </div>
                            ) : (
                              <button onClick={() => setDeleteConfirm(provider.provider_name as SocialProvider)} className="rounded-lg p-2 text-red-400 transition-colors hover:bg-red-50 hover:text-red-600" title="Delete"><Trash2 size={15} /></button>
                            )}
                          </div>
                        </div>
                      </DashboardPagePanel>
                    )
                  })}
                </div>
              )}

              {availableLoginProviders.length > 0 && (
                <div className="space-y-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Available Providers</p>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {availableLoginProviders.map(provider => {
                      const info = PROVIDER_INFO[provider]
                      return (
                        <button key={provider} onClick={() => { setCreatingProvider(provider); setCreateFormData({ client_id: '', client_secret: '', redirect_uri: redirectUriFor(provider, 'login') }) }} className="group text-left">
                          <DashboardPagePanel className="p-4 transition-shadow hover:shadow-md">
                            <div className="flex items-center gap-3 mb-2">
                              <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl border border-gray-100 bg-white shadow-sm">
                                <ProviderIcon provider={provider} size="sm" />
                              </div>
                              <span className="text-sm font-semibold text-gray-900">{info.name}</span>
                            </div>
                            <p className="text-xs text-gray-500 leading-relaxed">{info.description}</p>
                          </DashboardPagePanel>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}

              {providers.length === 0 && availableLoginProviders.length === 0 && (
                <DashboardPagePanel className="p-12 text-center"><p className="text-sm text-gray-500">All login providers are configured.</p></DashboardPagePanel>
              )}

              <DashboardPagePanel className="p-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-full bg-[#f1eadc] p-2 flex-shrink-0"><ShieldCheck className="h-4 w-4 text-[#7c5d45]" /></div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">About Login Providers</p>
                    <p className="mt-1 text-xs leading-relaxed text-gray-500">Configure OAuth providers to enable social login. Each provider requires credentials from its developer console. Disabled providers won't appear on the login page.</p>
                  </div>
                </div>
              </DashboardPagePanel>
            </div>
          )}

          {/* ── PLATFORM OAUTH APPS ──────────────────────────────────────── */}
          {activeTab === 'platform-oauth-apps' && (
            <div className="space-y-4">
              {platformLoading ? (
                <div className="flex justify-center py-16"><LoadingSpinner size="lg" /></div>
              ) : (
                <>
                  {platformApps.length > 0 && (
                    <div className="space-y-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Configured Apps</p>
                      {platformApps.map(app => {
                        const info = PLATFORM_PROVIDER_INFO[app.provider as PlatformProvider]
                        return (
                          <DashboardPagePanel key={app.id} className="overflow-hidden">
                            <div className="flex items-center gap-4 p-4">
                              <ProviderAvatar provider={app.provider} />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-sm font-semibold text-gray-900">{app.app_name}</span>
                                  <span className="text-xs text-gray-400">{info?.name ?? app.provider}</span>
                                  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${app.is_active ? 'bg-[#ebf5ee] text-[#24543b]' : 'bg-gray-100 text-gray-500'}`}>
                                    <span className={`h-1.5 w-1.5 rounded-full ${app.is_active ? 'bg-[#24543b]' : 'bg-gray-400'}`} />
                                    {app.is_active ? 'Enabled' : 'Disabled'}
                                  </span>
                                </div>
                                <div className="mt-0.5 flex flex-wrap gap-x-4 text-xs text-gray-500">
                                  <span>Client ID: <code className="font-mono">{app.client_id?.slice(0, 24)}…</code></span>
                                  {app.scopes?.length > 0 && <span className="hidden sm:inline">Scopes: {app.scopes.slice(0, 2).join(', ')}{app.scopes.length > 2 ? ` +${app.scopes.length - 2}` : ''}</span>}
                                </div>
                              </div>
                              <div className="flex items-center gap-1">
                                <button
                                  onClick={() => {
                                    setPlatformEditingApp(app)
                                    setPlatformEditForm({
                                      provider: app.provider,
                                      app_name: app.app_name,
                                      auth_method: (app as any).auth_method || 'oauth',
                                      client_id: app.client_id,
                                      client_secret: '',
                                      redirect_uri: app.redirect_uri,
                                      scopes: app.scopes || [],
                                      description: app.description || '',
                                    })
                                  }}
                                  className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700" title="Edit"
                                >
                                  <Edit2 size={15} />
                                </button>
                                <button onClick={() => handlePlatformToggle(app)} className={`rounded-lg p-2 transition-colors ${app.is_active ? 'text-gray-400 hover:bg-gray-100 hover:text-gray-700' : 'text-emerald-600 hover:bg-emerald-50'}`} title={app.is_active ? 'Disable' : 'Enable'}><Power size={15} /></button>
                                {platformDeleteConfirm === app.id ? (
                                  <div className="flex items-center gap-1.5 ml-1">
                                    <button onClick={() => handlePlatformDelete(app.id)} className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700 transition-colors">Confirm</button>
                                    <button onClick={() => setPlatformDeleteConfirm(null)} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-50 transition-colors">Cancel</button>
                                  </div>
                                ) : (
                                  <button onClick={() => setPlatformDeleteConfirm(app.id)} className="rounded-lg p-2 text-red-400 transition-colors hover:bg-red-50 hover:text-red-600" title="Delete"><Trash2 size={15} /></button>
                                )}
                              </div>
                            </div>
                          </DashboardPagePanel>
                        )
                      })}
                    </div>
                  )}

                  {availablePlatformProviders.length > 0 && (
                    <div className="space-y-3">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#9a7a5e]">Available Providers</p>
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {availablePlatformProviders.map(provider => {
                          const info = PLATFORM_PROVIDER_INFO[provider]
                          return (
                            <button key={provider} onClick={() => openPlatformCreate(provider)} className="group text-left">
                              <DashboardPagePanel className="p-4 transition-shadow hover:shadow-md">
                                <div className="flex items-center gap-3 mb-2">
                                  <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl text-xs font-bold ${info.bg} ${info.text}`}>{info.initials}</div>
                                  <span className="text-sm font-semibold text-gray-900">{info.name}</span>
                                </div>
                                <p className="text-xs text-gray-500 leading-relaxed">{info.description}</p>
                              </DashboardPagePanel>
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {platformApps.length === 0 && (
                    <DashboardPagePanel className="p-12 text-center">
                      <div className="mx-auto mb-4 inline-flex h-14 w-14 items-center justify-center rounded-full bg-[#f3ecde]"><Plus size={28} className="text-[#171717]" /></div>
                      <h3 className="text-base font-semibold text-gray-900">No platform OAuth apps</h3>
                      <p className="mt-2 text-sm text-gray-600 max-w-sm mx-auto">Add OAuth credentials to let tenants use Synkora-managed integrations.</p>
                    </DashboardPagePanel>
                  )}

                  <DashboardPagePanel className="p-4">
                    <div className="flex items-start gap-3">
                      <div className="rounded-full bg-[#f1eadc] p-2 flex-shrink-0"><ShieldCheck className="h-4 w-4 text-[#7c5d45]" /></div>
                      <div>
                        <p className="text-sm font-semibold text-gray-900">About Platform OAuth Apps</p>
                        <p className="mt-1 text-xs leading-relaxed text-gray-500">Platform OAuth apps let tenants use Synkora-owned credentials. Client secrets are encrypted at rest and never exposed via API.</p>
                      </div>
                    </div>
                  </DashboardPagePanel>
                </>
              )}
            </div>
          )}
        </div>
      </DashboardPageShell>

      {/* ── MODAL: Create Login Provider ───────────────────────────────────── */}
      {creatingProvider && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="w-full max-w-[940px] overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="sticky top-0 flex items-center justify-between border-b border-gray-100 bg-white px-6 py-4">
              <div>
                <h3 className="text-base font-semibold text-gray-900">Add {PROVIDER_INFO[creatingProvider].name}</h3>
                <p className="text-xs text-gray-500 mt-0.5">Configure your {PROVIDER_INFO[creatingProvider].name} OAuth credentials</p>
              </div>
              <button onClick={() => setCreatingProvider(null)} className="rounded-lg p-2 text-gray-400 hover:bg-gray-100"><X size={18} /></button>
            </div>
            <div className="p-6 space-y-4">
              <div className={sectionCls}>
                <h4 className="text-sm font-semibold text-gray-900 mb-3">OAuth Credentials</h4>
                <div className="space-y-4">
                  <div>
                    <label className={labelCls}>Client ID *</label>
                    <input type="text" value={createFormData.client_id} onChange={e => setCreateFormData({ ...createFormData, client_id: e.target.value })} className={inputCls} placeholder="Enter your OAuth client ID" />
                  </div>
                  <div>
                    <label className={labelCls}>Client Secret *</label>
                    <input type="password" value={createFormData.client_secret} onChange={e => setCreateFormData({ ...createFormData, client_secret: e.target.value })} className={inputCls} placeholder="Enter your OAuth client secret" />
                  </div>
                  <div>
                    <div className="mb-1.5 flex items-center justify-between">
                      <label className={labelCls} style={{marginBottom:0}}>Redirect URI</label>
                      <span className="rounded-full bg-[#ebf5ee] px-2 py-0.5 text-[10px] font-semibold text-[#24543b]">Auto-generated</span>
                    </div>
                    <input readOnly value={createFormData.redirect_uri} className={`${inputCls} cursor-default opacity-70`} />
                    <p className="mt-1.5 text-xs text-gray-500">Copy this URL into your {PROVIDER_INFO[creatingProvider].name} app settings</p>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t border-gray-100 px-6 py-4">
              <button onClick={() => setCreatingProvider(null)} disabled={saving} className="rounded-[1rem] border border-black/10 px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50">Cancel</button>
              <button onClick={handleCreate} disabled={saving || !createFormData.client_id || !createFormData.client_secret} className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white hover:bg-black disabled:opacity-50 disabled:cursor-not-allowed">
                {saving ? <><LoadingSpinner size="sm" />Creating…</> : 'Create Provider'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Edit Login Provider ──────────────────────────────────────── */}
      {editingProvider && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="w-full max-w-[940px] overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="sticky top-0 flex items-center justify-between border-b border-gray-100 bg-white px-6 py-4">
              <div>
                <h3 className="text-base font-semibold text-gray-900">Edit {PROVIDER_INFO[editingProvider].name}</h3>
                <p className="text-xs text-gray-500 mt-0.5">Update your OAuth credentials</p>
              </div>
              <button onClick={() => setEditingProvider(null)} className="rounded-lg p-2 text-gray-400 hover:bg-gray-100"><X size={18} /></button>
            </div>
            <div className="p-6 space-y-4">
              <div className={sectionCls}>
                <h4 className="text-sm font-semibold text-gray-900 mb-3">OAuth Credentials</h4>
                <div className="space-y-4">
                  <div>
                    <label className={labelCls}>Client ID *</label>
                    <input type="text" value={editFormData.client_id} onChange={e => setEditFormData({ ...editFormData, client_id: e.target.value })} className={inputCls} placeholder="Enter client ID" />
                  </div>
                  <div>
                    <label className={labelCls}>Client Secret</label>
                    <input type="password" value={editFormData.client_secret} onChange={e => setEditFormData({ ...editFormData, client_secret: e.target.value })} className={inputCls} placeholder="Leave blank to keep existing" />
                  </div>
                  <div>
                    <div className="mb-1.5 flex items-center justify-between">
                      <label className={labelCls} style={{marginBottom:0}}>Redirect URI</label>
                      <span className="rounded-full bg-[#ebf5ee] px-2 py-0.5 text-[10px] font-semibold text-[#24543b]">Auto-generated</span>
                    </div>
                    <input readOnly value={editFormData.redirect_uri} className={`${inputCls} cursor-default opacity-70`} />
                  </div>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t border-gray-100 px-6 py-4">
              <button onClick={() => setEditingProvider(null)} disabled={saving} className="rounded-[1rem] border border-black/10 px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50">Cancel</button>
              <button onClick={handleSaveEdit} disabled={saving || !editFormData.client_id} className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white hover:bg-black disabled:opacity-50 disabled:cursor-not-allowed">
                {saving ? <><LoadingSpinner size="sm" />Saving…</> : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Create Platform OAuth App ───────────────────────────────── */}
      {platformCreating && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="w-full max-w-[940px] max-h-[90vh] overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="sticky top-0 flex items-center justify-between border-b border-gray-100 bg-white px-6 py-4">
              <div>
                <h3 className="text-base font-semibold text-gray-900">Add Platform OAuth App</h3>
                <p className="text-xs text-gray-500 mt-0.5">Register a Synkora-owned OAuth app for tenant use</p>
              </div>
              <button onClick={() => setPlatformCreating(false)} className="rounded-lg p-2 text-gray-400 hover:bg-gray-100"><X size={18} /></button>
            </div>
            <div className="p-6 space-y-4">
              {/* Provider selection */}
              <div className={sectionCls}>
                <h4 className="text-sm font-semibold text-gray-900 mb-3">Provider</h4>
                <div>
                  <label className={labelCls}>Provider *</label>
                  <select value={platformCreateForm.provider} onChange={e => handlePlatformProviderChange(e.target.value)} className={selectCls}>
                    <option value="">Select a provider</option>
                    {PLATFORM_PROVIDERS.map(p => <option key={p} value={p}>{PLATFORM_PROVIDER_INFO[p].name}</option>)}
                  </select>
                </div>
              </div>

              {/* Connection Details */}
              <div className={sectionCls}>
                <h4 className="text-sm font-semibold text-gray-900 mb-3">Connection Details</h4>
                <div className="space-y-4">
                  <div>
                    <label className={labelCls}>App Name *</label>
                    <input type="text" value={platformCreateForm.app_name} onChange={e => setPlatformCreateForm(f => ({ ...f, app_name: e.target.value }))} className={inputCls} placeholder="e.g. Synkora Gmail" />
                  </div>
                  <div>
                    <label className={labelCls}>Description</label>
                    <input type="text" value={platformCreateForm.description} onChange={e => setPlatformCreateForm(f => ({ ...f, description: e.target.value }))} className={inputCls} placeholder="Optional description" />
                  </div>
                </div>
              </div>

              {/* Auth Method — only show for github */}
              {platformCreateForm.provider === 'github' && (
                <div className={sectionCls}>
                  <h4 className="text-sm font-semibold text-gray-900 mb-3">Authentication Method</h4>
                  <div className="space-y-2">
                    {(['oauth', 'api_token', 'github_app'] as const).map(method => (
                      <label key={method} className="flex items-start gap-3 rounded-[1rem] border border-black/10 bg-white/80 px-4 py-3 cursor-pointer hover:border-[#d7c6b4]">
                        <input
                          type="radio"
                          name="platform_auth_method_create"
                          value={method}
                          checked={platformCreateForm.auth_method === method}
                          onChange={() => setPlatformCreateForm(f => ({ ...f, auth_method: method }))}
                          className="mt-0.5 h-4 w-4 border-gray-300 text-[#10717C] focus:ring-[#79dfbc]"
                        />
                        <div>
                          <div className="text-sm font-semibold text-gray-900">
                            {method === 'oauth' ? 'OAuth App' : method === 'api_token' ? 'Personal Access Token' : 'GitHub App'}
                          </div>
                          <div className="text-xs text-gray-500">
                            {method === 'oauth' && 'Standard OAuth 2.0 — users authorize via browser redirect'}
                            {method === 'api_token' && 'A GitHub PAT stored as the API token'}
                            {method === 'github_app' && 'GitHub App with App ID + private key — installation looked up automatically from configured repos'}
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Credentials */}
              <div className={sectionCls}>
                <h4 className="text-sm font-semibold text-gray-900 mb-3">
                  {platformCreateForm.auth_method === 'github_app' ? 'GitHub App Credentials' : 'OAuth Credentials'}
                </h4>
                {platformCreateForm.auth_method === 'github_app' ? (
                  <div className="space-y-4">
                    <div>
                      <label className={labelCls}>App ID *</label>
                      <input type="text" value={platformCreateForm.client_id} onChange={e => setPlatformCreateForm(f => ({ ...f, client_id: e.target.value }))} className={inputCls} placeholder="123456" />
                      <p className="mt-1.5 text-xs text-gray-500">The numeric App ID from GitHub App settings</p>
                    </div>
                    <div>
                      <label className={labelCls}>Private Key (PEM) *</label>
                      <textarea rows={7} value={platformCreateForm.client_secret} onChange={e => setPlatformCreateForm(f => ({ ...f, client_secret: e.target.value }))} className={`${inputCls} font-mono text-xs`} placeholder={'-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----'} />
                      <p className="mt-1.5 text-xs text-gray-500">Paste the full PEM private key — encrypted and never returned by the API. The installation ID is resolved automatically from the repository.</p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <label className={labelCls}>Client ID *</label>
                      <input type="text" value={platformCreateForm.client_id} onChange={e => setPlatformCreateForm(f => ({ ...f, client_id: e.target.value }))} className={inputCls} placeholder="Enter your OAuth client ID" />
                    </div>
                    <div>
                      <label className={labelCls}>Client Secret *</label>
                      <input type="password" value={platformCreateForm.client_secret} onChange={e => setPlatformCreateForm(f => ({ ...f, client_secret: e.target.value }))} className={inputCls} placeholder="Enter your OAuth client secret" />
                      <p className="mt-1.5 text-xs text-gray-500">Encrypted and stored securely — never returned by the API</p>
                    </div>
                    <div>
                      <div className="mb-1.5 flex items-center justify-between">
                        <label className={labelCls} style={{marginBottom:0}}>Redirect URI</label>
                        <span className="rounded-full bg-[#ebf5ee] px-2 py-0.5 text-[10px] font-semibold text-[#24543b]">Auto-generated</span>
                      </div>
                      <input readOnly value={platformCreateForm.redirect_uri} className={`${inputCls} cursor-default opacity-70`} placeholder="Select a provider first" />
                      {platformCreateForm.redirect_uri && (
                        <p className="mt-1.5 text-xs text-gray-500">Copy this URL into your OAuth app's allowed redirect URIs</p>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Scopes — only for non-github_app */}
              {platformCreateForm.auth_method !== 'github_app' && (
                <div className={sectionCls}>
                  <h4 className="text-sm font-semibold text-gray-900 mb-1">Scopes</h4>
                  <p className="text-xs text-gray-500 mb-3">Select the permissions this app will request from users</p>
                  <ScopesField
                    scopes={platformCreateForm.scopes}
                    defaultScopes={PLATFORM_PROVIDER_INFO[platformCreateForm.provider as PlatformProvider]?.defaultScopes ?? []}
                    onChange={scopes => setPlatformCreateForm(f => ({ ...f, scopes }))}
                  />
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 border-t border-gray-100 px-6 py-4">
              <button onClick={() => setPlatformCreating(false)} disabled={platformSaving} className="rounded-[1rem] border border-black/10 px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50">Cancel</button>
              <button
                onClick={handlePlatformCreate}
                disabled={platformSaving || !platformCreateForm.provider || !platformCreateForm.app_name || !platformCreateForm.client_id || !platformCreateForm.client_secret}
                className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white hover:bg-black disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {platformSaving ? <><LoadingSpinner size="sm" />Creating…</> : 'Create App'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL: Edit Platform OAuth App ─────────────────────────────────── */}
      {platformEditingApp && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="w-full max-w-[940px] max-h-[90vh] overflow-y-auto rounded-2xl bg-white shadow-2xl">
            <div className="sticky top-0 flex items-center justify-between border-b border-gray-100 bg-white px-6 py-4">
              <div>
                <h3 className="text-base font-semibold text-gray-900">Edit {platformEditingApp.app_name}</h3>
                <p className="text-xs text-gray-500 mt-0.5">Update OAuth app credentials and settings</p>
              </div>
              <button onClick={() => setPlatformEditingApp(null)} className="rounded-lg p-2 text-gray-400 hover:bg-gray-100"><X size={18} /></button>
            </div>
            <div className="p-6 space-y-4">
              <div className={sectionCls}>
                <h4 className="text-sm font-semibold text-gray-900 mb-3">Connection Details</h4>
                <div className="space-y-4">
                  <div>
                    <label className={labelCls}>App Name *</label>
                    <input type="text" value={platformEditForm.app_name} onChange={e => setPlatformEditForm(f => ({ ...f, app_name: e.target.value }))} className={inputCls} />
                  </div>
                  <div>
                    <label className={labelCls}>Description</label>
                    <input type="text" value={platformEditForm.description} onChange={e => setPlatformEditForm(f => ({ ...f, description: e.target.value }))} className={inputCls} placeholder="Optional description" />
                  </div>
                </div>
              </div>

              <div className={sectionCls}>
                <h4 className="text-sm font-semibold text-gray-900 mb-3">
                  {platformEditForm.auth_method === 'github_app' ? 'GitHub App Credentials' : 'OAuth Credentials'}
                </h4>
                {platformEditForm.auth_method === 'github_app' ? (
                  <div className="space-y-4">
                    <div>
                      <label className={labelCls}>App ID *</label>
                      <input type="text" value={platformEditForm.client_id} onChange={e => setPlatformEditForm(f => ({ ...f, client_id: e.target.value }))} className={inputCls} placeholder="123456" />
                    </div>
                    <div>
                      <label className={labelCls}>Private Key (PEM)</label>
                      <textarea rows={7} value={platformEditForm.client_secret} onChange={e => setPlatformEditForm(f => ({ ...f, client_secret: e.target.value }))} className={`${inputCls} font-mono text-xs`} placeholder={'Leave blank to keep existing key\n-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----'} />
                      <p className="mt-1.5 text-xs text-gray-500">Only enter a new key to replace the existing one. Installation ID is resolved automatically from configured repositories.</p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <label className={labelCls}>Client ID *</label>
                      <input type="text" value={platformEditForm.client_id} onChange={e => setPlatformEditForm(f => ({ ...f, client_id: e.target.value }))} className={inputCls} />
                    </div>
                    <div>
                      <label className={labelCls}>Client Secret</label>
                      <input type="password" value={platformEditForm.client_secret} onChange={e => setPlatformEditForm(f => ({ ...f, client_secret: e.target.value }))} className={inputCls} placeholder="Leave blank to keep existing secret" />
                    </div>
                    <div>
                      <div className="mb-1.5 flex items-center justify-between">
                        <label className={labelCls} style={{marginBottom:0}}>Redirect URI</label>
                        <span className="rounded-full bg-[#ebf5ee] px-2 py-0.5 text-[10px] font-semibold text-[#24543b]">Auto-generated</span>
                      </div>
                      <input readOnly value={platformEditForm.redirect_uri} className={`${inputCls} cursor-default opacity-70`} />
                    </div>
                  </div>
                )}
              </div>

              <div className={sectionCls}>
                <h4 className="text-sm font-semibold text-gray-900 mb-1">Scopes</h4>
                <p className="text-xs text-gray-500 mb-3">Select the permissions this app will request from users</p>
                <ScopesField
                  scopes={platformEditForm.scopes}
                  defaultScopes={PLATFORM_PROVIDER_INFO[platformEditingApp.provider as PlatformProvider]?.defaultScopes ?? []}
                  onChange={scopes => setPlatformEditForm(f => ({ ...f, scopes }))}
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-gray-100 px-6 py-4">
              <button onClick={() => setPlatformEditingApp(null)} disabled={platformSaving} className="rounded-[1rem] border border-black/10 px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50">Cancel</button>
              <button
                onClick={handlePlatformSaveEdit}
                disabled={platformSaving || !platformEditForm.app_name || !platformEditForm.client_id}
                className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white hover:bg-black disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {platformSaving ? <><LoadingSpinner size="sm" />Saving…</> : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
