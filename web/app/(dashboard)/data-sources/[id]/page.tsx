'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import {
  ArrowLeft,
  Database,
  RefreshCw,
  Trash2,
  AlertCircle,
  CheckCircle,
  Clock,
  FileText,
  Calendar,
  Activity,
  Settings,
  Slack,
  Mail,
  TrendingUp,
  TrendingDown,
  History,
  Copy,
  Eye,
  EyeOff,
  Zap,
  ZapOff,
  Radio,
  Signal,
  SignalHigh,
  SignalLow,
  GitBranch,
  Inbox,
  CheckSquare,
  SkipForward,
  XCircle,
  BarChart2,
  KeyRound,
  ExternalLink,
  Webhook,
  Pencil,
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface DataSource {
  id: number
  name: string
  type: string
  knowledge_base_id: number | null
  tenant_id: string
  config: Record<string, any>
  status: string
  sync_enabled: boolean
  last_sync_at: string | null
  last_error: string | null
  total_documents: number
  created_at: string
  updated_at: string
}

interface SyncHistory {
  id: number
  started_at: string
  completed_at: string | null
  status: string
  documents_processed: number
  documents_added: number
  documents_updated: number
  documents_deleted: number
  documents_failed: number
  error_message: string | null
}

interface StreamHealth {
  stream_key: string
  stream_length: number
  pending_count: number
  consumer_group: string
  consumers: number
  webhook_url: string
  is_stream_active: boolean
}

const WEBHOOK_SOURCES = ['SLACK', 'GITHUB', 'GITLAB', 'JIRA', 'LINEAR', 'NOTION']

function useInterval(fn: () => void, ms: number | null) {
  const fnRef = useRef(fn)
  fnRef.current = fn
  useEffect(() => {
    if (ms === null) return
    const id = setInterval(() => fnRef.current(), ms)
    return () => clearInterval(id)
  }, [ms])
}

function StreamStat({
  label, value, icon, color, large = false,
}: {
  label: string
  value: number
  icon: React.ReactNode
  color: 'blue' | 'amber' | 'purple' | 'green'
  large?: boolean
}) {
  const bg: Record<string, string> = {
    blue: 'bg-blue-50', amber: 'bg-amber-50', purple: 'bg-purple-50', green: 'bg-green-50',
  }
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center gap-2 mb-3">
        <div className={`p-2 ${bg[color]} rounded-lg`}>{icon}</div>
        <p className="text-xs font-medium text-gray-500">{label}</p>
      </div>
      <p className={`font-bold text-gray-900 ${large ? 'text-3xl' : 'text-2xl'}`}>{value}</p>
    </div>
  )
}

export default function DataSourceDetailsPage() {
  const params = useParams()
  const router = useRouter()
  const id = params.id as string

  const [dataSource, setDataSource] = useState<DataSource | null>(null)
  const [syncHistory, setSyncHistory] = useState<SyncHistory[]>([])
  const [streamHealth, setStreamHealth] = useState<StreamHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [activating, setActivating] = useState(false)
  const [savingSecret, setSavingSecret] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'webhook' | 'stream' | 'history' | 'config'>('overview')
  const [deleteModal, setDeleteModal] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [editModal, setEditModal] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editName, setEditName] = useState('')
  const [editSyncEnabled, setEditSyncEnabled] = useState(true)
  const [editConfig, setEditConfig] = useState<Record<string, any>>({})
  const [signingSecret, setSigningSecret] = useState('')
  const [showSecret, setShowSecret] = useState(false)
  const [streamPolling, setStreamPolling] = useState(false)

  const fetchDataSource = useCallback(async () => {
    try {
      const data = await apiClient.getDataSource(id)
      setDataSource(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    }
  }, [id])

  const fetchSyncHistory = useCallback(async () => {
    try {
      const data = await apiClient.getDataSourceSyncHistory(id)
      setSyncHistory(Array.isArray(data) ? data : [])
    } catch {
      setSyncHistory([])
    }
  }, [id])

  const fetchStreamHealth = useCallback(async () => {
    try {
      const data = await apiClient.getStreamHealth(id)
      setStreamHealth(data)
    } catch {
      setStreamHealth(null)
    }
  }, [id])

  useEffect(() => {
    const init = async () => {
      setLoading(true)
      await fetchDataSource()
      await fetchSyncHistory()
      setLoading(false)
    }
    init()
  }, [fetchDataSource, fetchSyncHistory])

  useEffect(() => {
    if (activeTab === 'stream' || activeTab === 'webhook') {
      fetchStreamHealth()
      setStreamPolling(true)
    } else {
      setStreamPolling(false)
    }
  }, [activeTab, fetchStreamHealth])

  // Poll stream health every 3s when on stream/webhook tab
  useInterval(fetchStreamHealth, streamPolling ? 3000 : null)

  // Poll datasource when syncing
  useInterval(
    () => { fetchDataSource(); fetchSyncHistory() },
    dataSource?.status?.toUpperCase() === 'SYNCING' ? 4000 : null,
  )

  const handleSync = async () => {
    try {
      setSyncing(true)
      setError(null)
      await apiClient.syncDataSource(id)
      toast.success('Sync started')
      setTimeout(() => { fetchDataSource(); fetchSyncHistory(); setSyncing(false) }, 2000)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to trigger sync'
      setError(msg)
      toast.error(msg)
      setSyncing(false)
    }
  }

  const handleActivate = async () => {
    setActivating(true)
    try {
      const updated = await apiClient.activateDataSource(id)
      setDataSource(updated)
      toast.success('Data source activated — ready to receive webhook events')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Activation failed')
    } finally {
      setActivating(false)
    }
  }

  const handleDeactivate = async () => {
    setActivating(true)
    try {
      const updated = await apiClient.deactivateDataSource(id)
      setDataSource(updated)
      toast.success('Data source deactivated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Deactivation failed')
    } finally {
      setActivating(false)
    }
  }

  const handleSaveSecret = async () => {
    if (!signingSecret.trim()) { toast.error('Enter a signing secret'); return }
    setSavingSecret(true)
    try {
      const updated = await apiClient.updateDataSourceConfig(id, {
        ...(dataSource?.config ?? {}),
        signing_secret: signingSecret.trim(),
      })
      setDataSource(updated)
      toast.success('Signing secret saved')
      setSigningSecret('')
    } catch {
      toast.error('Failed to save signing secret')
    } finally {
      setSavingSecret(false)
    }
  }

  const openEditModal = () => {
    if (!dataSource) return
    setEditName(dataSource.name)
    setEditSyncEnabled(dataSource.sync_enabled)
    setEditConfig({ ...dataSource.config })
    setEditModal(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await apiClient.updateDataSource(id, {
        name: editName.trim(),
        config: editConfig,
        sync_enabled: editSyncEnabled,
      })
      setDataSource(updated)
      setEditModal(false)
      toast.success('Data source updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save changes')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await apiClient.deleteDataSource(id)
      toast.success('Data source deleted')
      router.push('/data-sources')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete')
      setDeleting(false)
    }
  }

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text)
    toast.success(`${label} copied`)
  }

  const getSourceIcon = (type: string) => {
    switch (type?.toUpperCase()) {
      case 'SLACK': return <Slack className="w-6 h-6" />
      case 'GMAIL': return <Mail className="w-6 h-6" />
      case 'GITHUB': return <GitBranch className="w-6 h-6" />
      default: return <Database className="w-6 h-6" />
    }
  }

  const getSourceColor = (type: string) => {
    switch (type?.toUpperCase()) {
      case 'SLACK': return 'bg-purple-100 text-purple-800'
      case 'GMAIL': return 'bg-red-100 text-red-800'
      case 'GITHUB': return 'bg-gray-100 text-gray-800'
      default: return 'bg-blue-100 text-blue-800'
    }
  }

  const getStatusBadge = (status: string) => {
    const s = status?.toUpperCase()
    const map: Record<string, { bg: string; icon: React.ReactNode; label: string }> = {
      ACTIVE:   { bg: 'bg-green-100 text-green-800',  icon: <CheckCircle className="w-3 h-3" />,            label: 'Active' },
      INACTIVE: { bg: 'bg-yellow-100 text-yellow-800', icon: <Clock className="w-3 h-3" />,                  label: 'Inactive' },
      SYNCING:  { bg: 'bg-blue-100 text-blue-800',     icon: <RefreshCw className="w-3 h-3 animate-spin" />, label: 'Syncing' },
      ERROR:    { bg: 'bg-red-100 text-red-800',       icon: <AlertCircle className="w-3 h-3" />,            label: 'Error' },
    }
    const cfg = map[s] ?? { bg: 'bg-gray-100 text-gray-700', icon: <Clock className="w-3 h-3" />, label: status }
    return (
      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${cfg.bg}`}>
        {cfg.icon}{cfg.label}
      </span>
    )
  }

  const getSyncBadge = (status: string) => {
    const s = status?.toLowerCase()
    if (s === 'completed')   return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"><CheckCircle className="w-3 h-3" />Completed</span>
    if (s === 'in_progress') return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"><RefreshCw className="w-3 h-3 animate-spin" />In Progress</span>
    if (s === 'failed')      return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"><AlertCircle className="w-3 h-3" />Failed</span>
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700"><Clock className="w-3 h-3" />{status}</span>
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    )
  }

  if (!dataSource) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/30 p-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-red-50 border-l-4 border-red-500 rounded-lg p-4 mb-6">
            <p className="text-red-700">{error || 'Data source not found'}</p>
          </div>
          <Link href="/data-sources" className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700">
            <ArrowLeft className="w-5 h-5" /> Back to Data Sources
          </Link>
        </div>
      </div>
    )
  }

  const isWebhookSource = WEBHOOK_SOURCES.includes(dataSource.type?.toUpperCase())
  const hasSigningSecret = !!(dataSource.config?.signing_secret)
  const isActive = dataSource.status?.toUpperCase() === 'ACTIVE'
  const hasError = dataSource.status?.toUpperCase() === 'ERROR'
  const isSyncing = dataSource.status?.toUpperCase() === 'SYNCING'
  // Manual "Sync Now" should be available for any connected source (ACTIVE/ERROR),
  // regardless of whether it was connected via an OAuth app, a linked Slack bot,
  // or a direct API token — the backend's trigger_sync endpoint only gates on status.
  const usePolling = !isWebhookSource || isActive || hasError

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/30 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">

        <Link href="/data-sources" className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 mb-6 text-sm font-medium">
          <ArrowLeft className="w-4 h-4" /> Back to Data Sources
        </Link>

        {/* ── Header ── */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 mb-6">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div className="flex items-start gap-4">
              <div className={`p-3 rounded-xl ${getSourceColor(dataSource.type)}`}>
                {getSourceIcon(dataSource.type)}
              </div>
              <div>
                <div className="flex items-center gap-3 mb-1 flex-wrap">
                  <h1 className="text-2xl font-bold text-gray-900">{dataSource.name}</h1>
                  {getStatusBadge(dataSource.status)}
                  {isSyncing && (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 animate-pulse">
                      <Radio className="w-3 h-3" /> Live syncing
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-500">{dataSource.type?.toUpperCase()} Data Source</p>
                {dataSource.knowledge_base_id && (
                  <Link href={`/knowledge-bases/${dataSource.knowledge_base_id}`} className="mt-1 text-sm text-blue-600 hover:text-blue-700 inline-flex items-center gap-1">
                    <Database className="w-3.5 h-3.5" /> View Knowledge Base
                  </Link>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {isWebhookSource && !isActive && hasSigningSecret && (
                <button onClick={handleActivate} disabled={activating} className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50">
                  {activating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                  Activate
                </button>
              )}
              {isWebhookSource && isActive && (
                <button onClick={handleDeactivate} disabled={activating} className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-amber-700 bg-amber-50 rounded-lg hover:bg-amber-100 transition-colors disabled:opacity-50">
                  <ZapOff className="w-4 h-4" /> Deactivate
                </button>
              )}
              {usePolling && (
                <button onClick={handleSync} disabled={syncing || isSyncing || !dataSource.sync_enabled} className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50">
                  <RefreshCw className={`w-4 h-4 ${(syncing || isSyncing) ? 'animate-spin' : ''}`} />
                  {syncing ? 'Syncing…' : 'Sync Now'}
                </button>
              )}
              <button onClick={openEditModal} className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors">
                <Pencil className="w-4 h-4" /> Edit
              </button>
              <button onClick={() => setDeleteModal(true)} className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors">
                <Trash2 className="w-4 h-4" /> Delete
              </button>
            </div>
          </div>

          {/* Banners */}
          {isWebhookSource && !hasSigningSecret && (
            <div className="mt-4 flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
              <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
              <p className="text-sm text-amber-800">
                <span className="font-semibold">Webhook not configured.</span>{' '}
                Go to the{' '}
                <button onClick={() => setActiveTab('webhook')} className="underline font-medium">Webhook Setup</button>{' '}
                tab to enter your signing secret and activate.
              </p>
            </div>
          )}
          {isWebhookSource && hasSigningSecret && !isActive && (
            <div className="mt-4 flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl">
              <CheckCircle className="w-5 h-5 text-blue-600 mt-0.5 shrink-0" />
              <p className="text-sm text-blue-800">
                <span className="font-semibold">Signing secret configured.</span> Click <strong>Activate</strong> above to start receiving events.
              </p>
            </div>
          )}
          {dataSource.last_error && (
            <div className="mt-4 flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-xl">
              <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-red-800">Last error</p>
                <p className="text-xs font-mono text-red-700 mt-1">{dataSource.last_error}</p>
              </div>
            </div>
          )}
        </div>

        {/* ── Stat Cards ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Documents', value: dataSource.total_documents, icon: <FileText className="w-5 h-5 text-blue-600" />, bg: 'bg-blue-50' },
            { label: 'Last Sync', value: dataSource.last_sync_at ? new Date(dataSource.last_sync_at).toLocaleDateString() : 'Never', icon: <Clock className="w-5 h-5 text-green-600" />, bg: 'bg-green-50' },
            { label: 'Auto Sync', value: dataSource.sync_enabled ? 'Enabled' : 'Disabled', icon: <Activity className="w-5 h-5 text-purple-600" />, bg: 'bg-purple-50' },
            { label: 'Created', value: new Date(dataSource.created_at).toLocaleDateString(), icon: <Calendar className="w-5 h-5 text-orange-600" />, bg: 'bg-orange-50' },
          ].map(({ label, value, icon, bg }) => (
            <div key={label} className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
              <div className="flex items-center gap-2 mb-2">
                <div className={`p-1.5 rounded-lg ${bg}`}>{icon}</div>
                <p className="text-xs font-medium text-gray-500">{label}</p>
              </div>
              <p className="text-lg font-bold text-gray-900">{String(value)}</p>
            </div>
          ))}
        </div>

        {/* ── Tabs ── */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200">
          <div className="border-b border-gray-100">
            <nav className="flex overflow-x-auto">
              {([
                { key: 'overview', label: 'Overview',      icon: <BarChart2 className="w-4 h-4" /> },
                ...(isWebhookSource ? [
                  { key: 'webhook', label: 'Webhook Setup', icon: <Webhook className="w-4 h-4" /> },
                  { key: 'stream',  label: 'Live Stream',   icon: <Radio className="w-4 h-4" /> },
                ] : []),
                { key: 'history', label: `History${syncHistory.length ? ` (${syncHistory.length})` : ''}`, icon: <History className="w-4 h-4" /> },
                { key: 'config',  label: 'Config',          icon: <Settings className="w-4 h-4" /> },
              ] as { key: string; label: string; icon: React.ReactNode }[]).map(tab => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key as typeof activeTab)}
                  className={`flex items-center gap-2 px-5 py-4 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
                    activeTab === tab.key
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                  {tab.key === 'stream' && streamHealth?.is_stream_active && (
                    <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  )}
                </button>
              ))}
            </nav>
          </div>

          <div className="p-6">

            {/* OVERVIEW */}
            {activeTab === 'overview' && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-base font-semibold text-gray-900 mb-4">Source Information</h2>
                  <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {[
                      ['Source Type', dataSource.type?.toUpperCase()],
                      ['Status', dataSource.status],
                      ['Knowledge Base ID', dataSource.knowledge_base_id ?? '—'],
                      ['Sync Enabled', dataSource.sync_enabled ? 'Yes' : 'No'],
                      ['Created', new Date(dataSource.created_at).toLocaleString()],
                      ['Updated', new Date(dataSource.updated_at).toLocaleString()],
                    ].map(([k, v]) => (
                      <div key={String(k)} className="bg-gray-50 rounded-xl p-4">
                        <dt className="text-xs font-medium text-gray-500 mb-1">{k}</dt>
                        <dd className="text-sm font-semibold text-gray-900">{String(v)}</dd>
                      </div>
                    ))}
                  </dl>
                </div>

                {isWebhookSource && streamHealth && (
                  <div>
                    <h2 className="text-base font-semibold text-gray-900 mb-4">Stream Health</h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <StreamStat label="Queued" value={streamHealth.stream_length} icon={<Inbox className="w-4 h-4 text-blue-600" />} color="blue" />
                      <StreamStat label="Pending ACK" value={streamHealth.pending_count} icon={<Clock className="w-4 h-4 text-amber-600" />} color="amber" />
                      <StreamStat label="Consumers" value={streamHealth.consumers} icon={<Activity className="w-4 h-4 text-purple-600" />} color="purple" />
                      <div className="bg-white rounded-xl border border-gray-200 p-5">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="p-2 bg-gray-50 rounded-lg"><SignalHigh className="w-4 h-4 text-gray-600" /></div>
                          <p className="text-xs font-medium text-gray-500">Stream</p>
                        </div>
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${streamHealth.is_stream_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                          {streamHealth.is_stream_active
                            ? <><span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />Active</>
                            : <><span className="w-2 h-2 rounded-full bg-gray-400" />Idle</>}
                        </span>
                      </div>
                    </div>
                    <button onClick={() => setActiveTab('stream')} className="mt-3 text-sm text-blue-600 hover:text-blue-700 font-medium inline-flex items-center gap-1">
                      View live stream <ExternalLink className="w-3 h-3" />
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* WEBHOOK SETUP */}
            {activeTab === 'webhook' && (
              <div className="space-y-5 max-w-2xl">
                <div>
                  <h2 className="text-base font-semibold text-gray-900 mb-1">Webhook Setup</h2>
                  <p className="text-sm text-gray-500">
                    Follow the steps below to connect {dataSource.type} to this data source.
                  </p>
                </div>

                {/* Step 1 */}
                <div className="rounded-xl border border-gray-200 p-5 space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center shrink-0">1</span>
                    <p className="text-sm font-semibold text-gray-900">Copy your webhook URL</p>
                  </div>
                  <p className="text-xs text-gray-500 pl-8">Paste this into your {dataSource.type} App → Event Subscriptions → Request URL:</p>
                  <div className="pl-8">
                    {streamHealth ? (
                      <div className="flex items-center gap-2 bg-gray-900 rounded-lg px-4 py-3">
                        <code className="text-sm text-green-400 font-mono flex-1 break-all">{streamHealth.webhook_url}</code>
                        <button onClick={() => copyToClipboard(streamHealth.webhook_url, 'Webhook URL')} className="shrink-0 p-1.5 hover:bg-gray-700 rounded-lg transition-colors" title="Copy">
                          <Copy className="w-4 h-4 text-gray-400" />
                        </button>
                      </div>
                    ) : (
                      <div className="h-10 bg-gray-100 rounded-lg animate-pulse" />
                    )}
                  </div>
                </div>

                {/* Step 2 */}
                <div className="rounded-xl border border-gray-200 p-5 space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center shrink-0">2</span>
                    <p className="text-sm font-semibold text-gray-900">Enter signing secret</p>
                  </div>
                  <p className="text-xs text-gray-500 pl-8">
                    Found in {dataSource.type} App → Basic Information → App Credentials → Signing Secret.
                  </p>
                  <div className="pl-8 space-y-2">
                    {hasSigningSecret && (
                      <div className="flex items-center gap-2 text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                        <CheckCircle className="w-3.5 h-3.5 shrink-0" /> Signing secret is saved. Enter a new value to replace it.
                      </div>
                    )}
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <input
                          type={showSecret ? 'text' : 'password'}
                          value={signingSecret}
                          onChange={e => setSigningSecret(e.target.value)}
                          placeholder="Paste signing secret…"
                          className="w-full pl-9 pr-10 py-2.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono"
                        />
                        <button type="button" onClick={() => setShowSecret(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                          {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                      <button onClick={handleSaveSecret} disabled={savingSecret || !signingSecret.trim()} className="px-4 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center gap-2">
                        {savingSecret ? <RefreshCw className="w-4 h-4 animate-spin" /> : 'Save'}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Step 3 */}
                <div className="rounded-xl border border-gray-200 p-5 space-y-3">
                  <div className="flex items-center gap-2">
                    <span className={`w-6 h-6 rounded-full text-white text-xs font-bold flex items-center justify-center shrink-0 ${hasSigningSecret ? 'bg-blue-600' : 'bg-gray-300'}`}>3</span>
                    <p className={`text-sm font-semibold ${hasSigningSecret ? 'text-gray-900' : 'text-gray-400'}`}>Activate</p>
                  </div>
                  <div className="pl-8">
                    {isActive ? (
                      <div className="flex items-center justify-between">
                        <span className="inline-flex items-center gap-2 text-sm font-medium text-green-700">
                          <CheckCircle className="w-5 h-5" /> Active and receiving events
                        </span>
                        <button onClick={handleDeactivate} disabled={activating} className="text-sm text-amber-600 hover:text-amber-700 font-medium">Deactivate</button>
                      </div>
                    ) : (
                      <button onClick={handleActivate} disabled={activating || !hasSigningSecret} className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                        {activating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                        {!hasSigningSecret ? 'Save signing secret first' : 'Activate Webhook'}
                      </button>
                    )}
                  </div>
                </div>

                {/* Slack checklist */}
                {dataSource.type?.toUpperCase() === 'SLACK' && (
                  <div className="rounded-xl bg-purple-50 border border-purple-100 p-5">
                    <p className="text-sm font-semibold text-purple-900 mb-3">Slack App configuration checklist</p>
                    <ul className="space-y-2 text-xs text-purple-800">
                      {[
                        'Enable Event Subscriptions in your Slack App',
                        'Paste the webhook URL above as the Request URL',
                        'Subscribe to bot events: message.channels, message.groups',
                        'Copy the Signing Secret from Basic Information → App Credentials',
                        'Install the app to your workspace',
                      ].map(item => (
                        <li key={item} className="flex items-start gap-2">
                          <CheckSquare className="w-3.5 h-3.5 mt-0.5 shrink-0 text-purple-600" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* LIVE STREAM */}
            {activeTab === 'stream' && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-gray-900">Live Stream Monitor</h2>
                    <p className="text-xs text-gray-500 mt-0.5">Auto-refreshes every 3 seconds</p>
                  </div>
                  <span className="flex items-center gap-2 text-xs text-green-600 font-medium">
                    <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" /> Live
                  </span>
                </div>

                {!streamHealth ? (
                  <div className="text-center py-16 bg-gray-50 rounded-xl border-2 border-dashed border-gray-200">
                    <Signal className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                    <p className="text-gray-500 font-medium">Stream data unavailable</p>
                    <p className="text-xs text-gray-400 mt-1">Make sure this data source is linked to a knowledge base.</p>
                  </div>
                ) : (
                  <>
                    {/* Stream key bar */}
                    <div className="flex items-center gap-3 bg-gray-900 text-green-400 font-mono text-sm rounded-xl px-5 py-3">
                      <Radio className="w-4 h-4 shrink-0" />
                      <span className="flex-1 text-xs md:text-sm">{streamHealth.stream_key}</span>
                      <button onClick={() => copyToClipboard(streamHealth.stream_key, 'Stream key')} className="hover:text-green-200 transition-colors">
                        <Copy className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Big counters */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <StreamStat label="In Queue" value={streamHealth.stream_length} icon={<Inbox className="w-5 h-5 text-blue-600" />} color="blue" large />
                      <StreamStat label="Pending ACK" value={streamHealth.pending_count} icon={<Clock className="w-5 h-5 text-amber-600" />} color="amber" large />
                      <StreamStat label="Consumers" value={streamHealth.consumers} icon={<Activity className="w-5 h-5 text-purple-600" />} color="purple" large />
                      <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col justify-between">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="p-2 bg-gray-50 rounded-lg"><SignalHigh className="w-5 h-5 text-gray-600" /></div>
                          <p className="text-xs font-medium text-gray-500">Stream Status</p>
                        </div>
                        <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold w-fit ${streamHealth.is_stream_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                          {streamHealth.is_stream_active
                            ? <><span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />Active</>
                            : <><span className="w-2 h-2 rounded-full bg-gray-400" />Idle</>}
                        </span>
                      </div>
                    </div>

                    {/* Consumer group info */}
                    <div className="bg-gray-50 rounded-xl border border-gray-200 p-5">
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Consumer Group</p>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Group</p>
                          <p className="font-mono font-semibold text-gray-900">{streamHealth.consumer_group}</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500 mb-1">Active consumers</p>
                          <p className="font-semibold text-gray-900">{streamHealth.consumers}</p>
                        </div>
                      </div>
                    </div>

                    {/* Pending warning */}
                    {streamHealth.pending_count > 0 && (
                      <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
                        <Clock className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-sm font-semibold text-amber-800">{streamHealth.pending_count} messages pending acknowledgement</p>
                          <p className="text-xs text-amber-700 mt-0.5">
                            Messages delivered to a consumer but not yet ACKed. They will be reprocessed if the consumer crashes or restarts.
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Idle info */}
                    {!streamHealth.is_stream_active && (
                      <div className="flex items-start gap-3 p-4 bg-gray-50 border border-gray-200 rounded-xl">
                        <SignalLow className="w-5 h-5 text-gray-400 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-sm font-semibold text-gray-600">Stream is idle</p>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {isActive
                              ? 'No events in the queue. Events appear here as they arrive from your integration.'
                              : 'Activate this data source to start receiving events.'}
                          </p>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {/* SYNC HISTORY */}
            {activeTab === 'history' && (
              <div className="space-y-4">
                {isSyncing && (
                  <div className="flex items-center gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl">
                    <RefreshCw className="w-5 h-5 text-blue-600 animate-spin shrink-0" />
                    <div>
                      <p className="text-sm font-semibold text-blue-800">Sync in progress</p>
                      <p className="text-xs text-blue-600 mt-0.5">Auto-refreshing every 4s. Results will appear when complete.</p>
                    </div>
                  </div>
                )}

                {syncHistory.length === 0 ? (
                  <div className="text-center py-16 bg-gray-50 rounded-xl border-2 border-dashed border-gray-200">
                    <History className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                    <p className="text-gray-500 font-medium">No sync history yet</p>
                    <p className="text-xs text-gray-400 mt-1">Sync runs will appear here</p>
                  </div>
                ) : (
                  syncHistory.map(sync => (
                    <div key={sync.id} className="bg-gray-50 rounded-xl border border-gray-200 p-5 hover:border-blue-200 transition-colors">
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <p className="text-sm font-semibold text-gray-900">{new Date(sync.started_at).toLocaleString()}</p>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {sync.completed_at
                              ? `Duration: ${Math.round((new Date(sync.completed_at).getTime() - new Date(sync.started_at).getTime()) / 1000)}s`
                              : 'In progress…'}
                          </p>
                        </div>
                        {getSyncBadge(sync.status)}
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {[
                          { label: 'Processed', value: sync.documents_processed, color: 'text-gray-900', icon: <FileText className="w-3.5 h-3.5 text-gray-400" /> },
                          { label: 'Added', value: sync.documents_added, color: 'text-green-700', icon: <TrendingUp className="w-3.5 h-3.5 text-green-500" /> },
                          { label: 'Updated', value: sync.documents_updated, color: 'text-blue-700', icon: <SkipForward className="w-3.5 h-3.5 text-blue-400" /> },
                          { label: 'Failed', value: sync.documents_failed, color: 'text-red-700', icon: <TrendingDown className="w-3.5 h-3.5 text-red-400" /> },
                        ].map(({ label, value, color, icon }) => (
                          <div key={label} className="bg-white rounded-lg border border-gray-100 p-3">
                            <div className="flex items-center gap-1 mb-1">{icon}<p className="text-xs text-gray-500">{label}</p></div>
                            <p className={`text-xl font-bold ${color}`}>{value}</p>
                          </div>
                        ))}
                      </div>
                      {sync.error_message && (
                        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                          <p className="text-xs font-mono text-red-700">{sync.error_message}</p>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {/* CONFIG */}
            {activeTab === 'config' && (
              <div>
                <h2 className="text-base font-semibold text-gray-900 mb-4">Configuration</h2>
                {Object.keys(dataSource.config).length === 0 ? (
                  <div className="text-center py-12 bg-gray-50 rounded-xl border-2 border-dashed border-gray-200">
                    <Settings className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                    <p className="text-gray-500">No configuration set</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {Object.entries(dataSource.config).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between py-3 px-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
                        <span className="text-sm font-medium text-gray-700 capitalize">{key.replace(/_/g, ' ')}</span>
                        <span className="text-sm font-mono text-gray-900 max-w-xs truncate">
                          {key.includes('secret') || key.includes('token') ? '••••••••' : String(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

          </div>
        </div>
      </div>

      {/* Edit Modal */}
      {editModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Edit Data Source</h3>
              <button onClick={() => setEditModal(false)} className="text-gray-400 hover:text-gray-600">
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                type="text"
                value={editName}
                onChange={e => setEditName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium text-gray-700">Auto Sync</p>
                <p className="text-xs text-gray-500">Automatically sync on schedule</p>
              </div>
              <button
                onClick={() => setEditSyncEnabled(v => !v)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${editSyncEnabled ? 'bg-blue-600' : 'bg-gray-300'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${editSyncEnabled ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>

            {dataSource.type?.toUpperCase() === 'SLACK' && (
              <div className="space-y-3 border-t pt-4">
                <p className="text-sm font-semibold text-gray-700">Slack Settings</p>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Channels (comma-separated)</label>
                  <input
                    type="text"
                    value={editConfig.channels || ''}
                    onChange={e => setEditConfig({ ...editConfig, channels: e.target.value })}
                    placeholder="e.g. general, engineering"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Sync Frequency (seconds)</label>
                  <input
                    type="number"
                    min={60}
                    value={editConfig.sync_frequency || 3600}
                    onChange={e => setEditConfig({ ...editConfig, sync_frequency: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div className="flex gap-6">
                  <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                    <input type="checkbox" checked={editConfig.include_threads ?? true} onChange={e => setEditConfig({ ...editConfig, include_threads: e.target.checked })} className="w-4 h-4 rounded text-blue-600" />
                    Include threads
                  </label>
                  <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                    <input type="checkbox" checked={editConfig.include_files ?? true} onChange={e => setEditConfig({ ...editConfig, include_files: e.target.checked })} className="w-4 h-4 rounded text-blue-600" />
                    Include files
                  </label>
                </div>
              </div>
            )}

            {dataSource.type?.toUpperCase() === 'GMAIL' && (
              <div className="space-y-3 border-t pt-4">
                <p className="text-sm font-semibold text-gray-700">Gmail Settings</p>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Labels (comma-separated)</label>
                  <input type="text" value={editConfig.labels || ''} onChange={e => setEditConfig({ ...editConfig, labels: e.target.value })} placeholder="e.g. INBOX, IMPORTANT" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Search Query</label>
                  <input type="text" value={editConfig.query || ''} onChange={e => setEditConfig({ ...editConfig, query: e.target.value })} placeholder="e.g. from:example@gmail.com" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Sync Frequency (seconds)</label>
                  <input type="number" min={60} value={editConfig.sync_frequency || 3600} onChange={e => setEditConfig({ ...editConfig, sync_frequency: parseInt(e.target.value) })} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>
            )}

            <div className="flex gap-3 justify-end pt-2">
              <button onClick={() => setEditModal(false)} disabled={saving} className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50">Cancel</button>
              <button onClick={handleSave} disabled={saving || !editName.trim()} className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2">
                {saving ? <><RefreshCw className="w-4 h-4 animate-spin" />Saving…</> : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {deleteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-red-100 rounded-xl"><AlertCircle className="w-6 h-6 text-red-600" /></div>
              <h3 className="text-lg font-semibold text-gray-900">Delete Data Source</h3>
            </div>
            <p className="text-sm text-gray-600 mb-6">
              Are you sure you want to delete <strong>{dataSource.name}</strong>? This cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setDeleteModal(false)} disabled={deleting} className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50">Cancel</button>
              <button onClick={handleDelete} disabled={deleting} className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center gap-2">
                {deleting ? <><RefreshCw className="w-4 h-4 animate-spin" />Deleting…</> : <><Trash2 className="w-4 h-4" />Delete</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
