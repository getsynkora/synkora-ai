'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  Database,
  Plus,
  Trash2,
  Eye,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Clock,
  Search,
  Filter,
  FileText,
  Slack,
  Mail,
  GitBranch,
  Webhook,
  Radio,
  ChevronRight,
  Home,
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface DataSource {
  id: number
  name: string
  type: string
  knowledge_base_id: number
  knowledge_base_name?: string
  config: Record<string, any>
  status: string
  sync_enabled: boolean
  last_sync_at: string | null
  last_error: string | null
  total_documents: number
  created_at: string
  updated_at: string
}

const WEBHOOK_SOURCES = ['SLACK', 'GITHUB', 'GITLAB', 'JIRA', 'LINEAR', 'NOTION']

export default function DataSourcesPage() {
  const [dataSources, setDataSources] = useState<DataSource[]>([])
  const [filteredSources, setFilteredSources] = useState<DataSource[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [deleteModal, setDeleteModal] = useState<{ show: boolean; source: DataSource | null }>({
    show: false,
    source: null,
  })
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    fetchDataSources()
  }, [])

  useEffect(() => {
    filterDataSources()
  }, [searchQuery, filterType, filterStatus, dataSources])

  const fetchDataSources = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getDataSources()
      setDataSources(Array.isArray(data) ? data : [])
    } catch (err) {
      const message = err instanceof Error ? err.message : 'An error occurred'
      setError(message)
      toast.error('Failed to load data sources')
    } finally {
      setLoading(false)
    }
  }

  const filterDataSources = () => {
    let filtered = dataSources

    if (searchQuery) {
      filtered = filtered.filter(source =>
        source.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        source.type?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    if (filterType !== 'all') {
      filtered = filtered.filter(source => source.type === filterType)
    }

    if (filterStatus !== 'all') {
      filtered = filtered.filter(source => source.status === filterStatus)
    }

    setFilteredSources(filtered)
  }

  const openDeleteModal = (source: DataSource) => {
    setDeleteModal({ show: true, source })
  }

  const closeDeleteModal = () => {
    setDeleteModal({ show: false, source: null })
  }

  const confirmDelete = async () => {
    if (!deleteModal.source) return

    setDeleting(true)
    try {
      await apiClient.deleteDataSource(deleteModal.source.id.toString())
      toast.success('Data source deleted successfully')
      closeDeleteModal()
      fetchDataSources()
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete data source'
      toast.error(errorMessage)
    } finally {
      setDeleting(false)
    }
  }

  const getSourceIcon = (sourceType: string) => {
    switch (sourceType?.toUpperCase()) {
      case 'SLACK':
        return <Slack className="h-5 w-5" />
      case 'GMAIL':
        return <Mail className="h-5 w-5" />
      case 'GITHUB':
      case 'GITLAB':
        return <GitBranch className="h-5 w-5" />
      default:
        return <Database className="h-5 w-5" />
    }
  }

  const getSourceColor = (sourceType: string) => {
    switch (sourceType?.toUpperCase()) {
      case 'SLACK':
        return 'bg-sand-deep text-ink-soft'
      case 'GMAIL':
        return 'bg-blush-wash text-leaf'
      case 'GITHUB':
      case 'GITLAB':
        return 'bg-sand-deep text-ink-soft'
      default:
        return 'bg-leaf-wash text-steel'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'ACTIVE':
        return 'bg-leaf-wash text-leaf'
      case 'SYNCING':
        return 'bg-leaf-wash text-steel'
      case 'INACTIVE':
        return 'bg-sand text-gold'
      case 'ERROR':
        return 'bg-blush-wash text-danger'
      default:
        return 'bg-sand-deep text-ink-mute'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'ACTIVE':
        return <CheckCircle className="h-3 w-3" />
      case 'SYNCING':
        return <RefreshCw className="h-3 w-3 motion-safe:animate-spin" />
      case 'ERROR':
        return <AlertCircle className="h-3 w-3" />
      default:
        return <Clock className="h-3 w-3" />
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never'

    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  const uniqueTypes = Array.from(new Set(dataSources.map(s => s.type)))
  const uniqueStatuses = Array.from(new Set(dataSources.map(s => s.status)))
  const searchFieldClass = 'w-full rounded-[1.2rem] border border-black/10 bg-white/80 py-3 pl-11 pr-4 text-sm text-ink shadow-soft transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-leaf focus:outline-none focus:ring-2 focus:ring-leaf/15'
  const filterFieldClass = 'rounded-[1rem] border border-black/10 bg-white px-3 py-2.5 text-sm text-ink-soft shadow-soft transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-leaf focus:outline-none focus:ring-2 focus:ring-leaf/15'
  const totalDocuments = dataSources.reduce((sum, source) => sum + source.total_documents, 0)
  const activeSources = dataSources.filter(source => source.status?.toUpperCase() === 'ACTIVE').length
  const syncingSources = dataSources.filter(source => source.status?.toUpperCase() === 'SYNCING').length

  if (loading) {
    return (
      <div className="dashboard-resource-page flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 motion-safe:animate-spin rounded-full border-b-2 border-danger"></div>
          <p className="text-ink-soft">Loading your data sources…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-4 flex items-center gap-1.5 text-sm">
          <Link href="/" className="flex items-center gap-1 text-ink-mute transition-colors hover:text-ink">
            <Home className="h-3.5 w-3.5" />
            Home
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-ash" />
          <span className="font-medium text-ink">Data Sources</span>
        </div>

        <div className="mb-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-extrabold tracking-tight text-ink md:text-3xl">Connected Sources</h1>
              <p className="mt-1 hidden text-sm text-ink-soft sm:block">
                Manage synced data sources that feed your knowledge bases
              </p>
            </div>
            <Link
              href="/data-sources/connect"
              className="inline-flex flex-shrink-0 items-center gap-2 rounded-[1rem] bg-ink px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
            >
              <Plus className="h-4 w-4 md:h-5 md:w-5" />
              <span className="hidden sm:inline">Connect Source</span>
              <span className="sm:hidden">Connect</span>
            </Link>
          </div>

          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-soft">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-sand p-2.5">
                  <Database className="h-[18px] w-[18px] text-ink" />
                </div>
                <div>
                  <p className="text-xs font-medium text-ink-mute">Total Sources</p>
                  <p className="mt-1 text-2xl font-semibold text-ink">{dataSources.length}</p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-soft">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-leaf-wash p-2.5">
                  <CheckCircle className="h-[18px] w-[18px] text-leaf" />
                </div>
                <div>
                  <p className="text-xs font-medium text-ink-mute">Active</p>
                  <p className="mt-1 text-2xl font-semibold text-ink">{activeSources}</p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-soft">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-leaf-wash p-2.5">
                  <FileText className="h-[18px] w-[18px] text-steel" />
                </div>
                <div>
                  <p className="text-xs font-medium text-ink-mute">Documents</p>
                  <p className="mt-1 text-2xl font-semibold text-ink">{totalDocuments}</p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-soft">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-sand p-2.5">
                  <RefreshCw className="h-[18px] w-[18px] text-gold" />
                </div>
                <div>
                  <p className="text-xs font-medium text-ink-mute">Syncing</p>
                  <p className="mt-1 text-2xl font-semibold text-ink">{syncingSources}</p>
                </div>
              </div>
            </div>
          </div>

          {dataSources.length > 0 && (
            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-3.5 shadow-soft">
              <div className="flex flex-col gap-3 md:flex-row">
                <div className="relative flex-1">
                  <Search className="absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-ash" />
                  <input
                    type="text"
                    placeholder="Search data sources…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className={searchFieldClass}
                  />
                </div>
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4 text-ash" />
                  <select
                    value={filterType}
                    onChange={(e) => setFilterType(e.target.value)}
                    className={filterFieldClass}
                  >
                    <option value="all">All Types</option>
                    {uniqueTypes.map(type => (
                      <option key={`type-${type}`} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                  <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className={filterFieldClass}
                  >
                    <option value="all">All Statuses</option>
                    {uniqueStatuses.map(status => (
                      <option key={`status-${status}`} value={status}>
                        {status}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="mb-6 rounded-[1.3rem] border border-blush bg-blush-wash/90 p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-danger" />
              <p className="text-danger">{error}</p>
            </div>
          </div>
        )}

        {filteredSources.length === 0 ? (
          <div className="rounded-[2rem] border border-black/10 bg-white/80 p-10 text-center shadow-soft">
            <div className="relative mx-auto mb-6 h-28 w-28">
              <div className="absolute inset-0 rotate-6 rounded-[1.75rem] bg-sand"></div>
              <div className="absolute inset-0 flex items-center justify-center rounded-[1.75rem] border border-black/10 bg-white shadow-soft">
                <Database className="h-10 w-10 text-leaf" />
              </div>
            </div>

            <h3 className="mb-2 text-xl font-semibold text-ink">
              {dataSources.length === 0 ? 'Connect your first data source' : 'No results found'}
            </h3>
            <p className="mx-auto mb-6 max-w-md text-ink-soft">
              {dataSources.length === 0
                ? 'Connect Slack, email, repositories, or other systems so your knowledge bases stay fresh and useful.'
                : 'Try adjusting your search or filters to find what you are looking for.'}
            </p>
            {dataSources.length === 0 && (
              <Link
                href="/data-sources/connect"
                className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
              >
                <Plus className="h-5 w-5" />
                Connect Data Source
              </Link>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredSources.map((source) => (
              <div
                key={source.id}
                className="group relative flex min-h-[292px] flex-col rounded-[1.7rem] border border-black/10 bg-white/80 shadow-soft transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:-translate-y-0.5 hover:border-black/15 hover:shadow-soft"
              >
                <div className="absolute right-4 top-4 z-20">
                  <button
                    type="button"
                    onClick={() => openDeleteModal(source)}
                    className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-blush bg-blush-wash/90 text-danger shadow-soft transition-colors hover:bg-blush-wash"
                    aria-label={`Delete ${source.name || source.type || 'data source'}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                <Link
                  href={`/data-sources/${source.id}`}
                  className="flex flex-1 flex-col p-5 pr-16 focus:outline-none"
                  aria-label={`Open ${source.name || source.type || 'data source'}`}
                >
                  <div className="mb-4 flex items-start gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                      <div className={`rounded-[1.1rem] p-3 transition-colors group-hover:opacity-90 ${getSourceColor(source.type)}`}>
                        {getSourceIcon(source.type)}
                      </div>
                      <div className="min-w-0">
                        <h3 className="truncate text-[1.05rem] font-semibold text-ink">
                          {source.name || source.type?.toUpperCase() || 'UNKNOWN'}
                        </h3>
                        <p className="mt-1 text-sm font-medium text-leaf">
                          {source.knowledge_base_name || `KB #${source.knowledge_base_id}`}
                        </p>
                      </div>
                    </div>
                    <span className="inline-flex items-center rounded-full bg-sand-deep px-2.5 py-1 text-[11px] font-medium text-ink-mute">
                      {source.type?.toUpperCase() || 'SOURCE'}
                    </span>
                  </div>

                  <div className="mb-4 flex flex-wrap items-center gap-2">
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ${getStatusColor(source.status)}`}>
                      {getStatusIcon(source.status)}
                      {source.status?.toUpperCase()}
                    </span>
                    {WEBHOOK_SOURCES.includes(source.type?.toUpperCase()) && !source.config?.signing_secret && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-sand px-2.5 py-1 text-[11px] font-medium text-gold">
                        <Webhook className="h-3 w-3" />
                        Setup needed
                      </span>
                    )}
                    {source.status?.toUpperCase() === 'SYNCING' && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-leaf-wash px-2.5 py-1 text-[11px] font-medium text-steel">
                        <Radio className="h-3 w-3" />
                        Live
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-3 gap-2.5">
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-cream px-3 py-3">
                      <div className="mb-1 flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5 text-ash" />
                        <p className="text-[10px] font-medium text-ink-mute">Documents</p>
                      </div>
                      <p className="text-base font-semibold text-ink">{source.total_documents}</p>
                    </div>
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-leaf-wash px-3 py-3">
                      <div className="mb-1 flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5 text-ash" />
                        <p className="text-[10px] font-medium text-ink-mute">Last Sync</p>
                      </div>
                      <p className="text-sm font-semibold text-ink">
                        {formatDate(source.last_sync_at)}
                      </p>
                    </div>
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-paper px-3 py-3">
                      <div className="mb-1 text-[10px] font-medium text-ink-mute">Knowledge Base</div>
                      <p className="truncate text-sm font-semibold text-ink">
                        {source.knowledge_base_name || `KB #${source.knowledge_base_id}`}
                      </p>
                    </div>
                  </div>
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>

      {deleteModal.show && deleteModal.source && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-[1.8rem] border border-black/10 bg-cream p-6 shadow-soft">
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-[1rem] bg-sand-deep p-2.5">
                <AlertCircle className="h-6 w-6 text-danger" />
              </div>
              <h3 className="text-lg font-semibold text-ink">Delete Data Source</h3>
            </div>

            <p className="mb-6 text-ink-soft">
              Are you sure you want to delete the <span className="font-semibold">{deleteModal.source.name}</span> data source?
              This action cannot be undone and will permanently delete all associated documents.
            </p>

            <div className="flex justify-end gap-3">
              <button
                onClick={closeDeleteModal}
                disabled={deleting}
                className="rounded-[1rem] bg-sand-deep px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-line disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="flex items-center gap-2 rounded-[1rem] bg-danger px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-danger disabled:opacity-50"
              >
                {deleting ? (
                  <>
                    <div className="h-4 w-4 motion-safe:animate-spin rounded-full border-2 border-white border-t-transparent" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="h-4 w-4" />
                    Delete
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
