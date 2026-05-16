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
        return 'bg-[#f6edf1] text-[#8b5a74]'
      case 'GMAIL':
        return 'bg-[#fbe9e7] text-[#b5533f]'
      case 'GITHUB':
      case 'GITLAB':
        return 'bg-[#f1eadc] text-[#5b564e]'
      default:
        return 'bg-[#edf4f6] text-[#486c77]'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'ACTIVE':
        return 'bg-[#e8f4ee] text-[#2d8b69]'
      case 'SYNCING':
        return 'bg-[#edf4f6] text-[#486c77]'
      case 'INACTIVE':
        return 'bg-[#f8f0dd] text-[#9a6700]'
      case 'ERROR':
        return 'bg-red-50 text-red-700'
      default:
        return 'bg-[#f1eadc] text-[#6e675d]'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'ACTIVE':
        return <CheckCircle className="h-3 w-3" />
      case 'SYNCING':
        return <RefreshCw className="h-3 w-3 animate-spin" />
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
  const searchFieldClass = 'w-full rounded-[1.2rem] border border-black/10 bg-white/80 py-3 pl-11 pr-4 text-sm text-gray-900 shadow-[0_12px_28px_rgba(0,0,0,0.04)] transition-all focus:border-[#2d8b69] focus:outline-none focus:ring-2 focus:ring-[#2d8b69]/15'
  const filterFieldClass = 'rounded-[1rem] border border-black/10 bg-white px-3 py-2.5 text-sm text-gray-700 shadow-[0_8px_18px_rgba(0,0,0,0.04)] transition-all focus:border-[#2d8b69] focus:outline-none focus:ring-2 focus:ring-[#2d8b69]/15'
  const totalDocuments = dataSources.reduce((sum, source) => sum + source.total_documents, 0)
  const activeSources = dataSources.filter(source => source.status?.toUpperCase() === 'ACTIVE').length
  const syncingSources = dataSources.filter(source => source.status?.toUpperCase() === 'SYNCING').length

  if (loading) {
    return (
      <div className="dashboard-resource-page flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-red-600"></div>
          <p className="text-gray-600">Loading your data sources...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="mx-auto max-w-6xl">
        <div className="mb-4 flex items-center gap-1.5 text-sm">
          <Link href="/" className="flex items-center gap-1 text-gray-500 transition-colors hover:text-[#171717]">
            <Home className="h-3.5 w-3.5" />
            Home
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-gray-400" />
          <span className="font-medium text-gray-900">Data Sources</span>
        </div>

        <div className="mb-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-extrabold tracking-tight text-gray-900 md:text-3xl">Connected Sources</h1>
              <p className="mt-1 hidden text-sm text-gray-600 sm:block">
                Manage synced data sources that feed your knowledge bases
              </p>
            </div>
            <Link
              href="/data-sources/connect"
              className="inline-flex flex-shrink-0 items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
            >
              <Plus className="h-4 w-4 md:h-5 md:w-5" />
              <span className="hidden sm:inline">Connect Source</span>
              <span className="sm:hidden">Connect</span>
            </Link>
          </div>

          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f3ecde] p-2.5">
                  <Database className="h-[18px] w-[18px] text-[#171717]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Total Sources</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">{dataSources.length}</p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#e8f4ee] p-2.5">
                  <CheckCircle className="h-[18px] w-[18px] text-[#2d8b69]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Active</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">{activeSources}</p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#edf4f6] p-2.5">
                  <FileText className="h-[18px] w-[18px] text-[#486c77]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Documents</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">{totalDocuments}</p>
                </div>
              </div>
            </div>

            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-4 shadow-[0_16px_35px_rgba(0,0,0,0.05)]">
              <div className="flex items-center gap-3">
                <div className="rounded-[1rem] bg-[#f8f0dd] p-2.5">
                  <RefreshCw className="h-[18px] w-[18px] text-[#9a6700]" />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-gray-500">Syncing</p>
                  <p className="mt-1 text-2xl font-semibold text-gray-900">{syncingSources}</p>
                </div>
              </div>
            </div>
          </div>

          {dataSources.length > 0 && (
            <div className="rounded-[1.4rem] border border-black/10 bg-white/80 p-3.5 shadow-[0_12px_28px_rgba(0,0,0,0.04)]">
              <div className="flex flex-col gap-3 md:flex-row">
                <div className="relative flex-1">
                  <Search className="absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search data sources..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className={searchFieldClass}
                  />
                </div>
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4 text-gray-400" />
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
          <div className="mb-6 rounded-[1.3rem] border border-red-200 bg-red-50/90 p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-red-600" />
              <p className="text-red-700">{error}</p>
            </div>
          </div>
        )}

        {filteredSources.length === 0 ? (
          <div className="rounded-[2rem] border border-black/10 bg-white/80 p-10 text-center shadow-[0_22px_55px_rgba(0,0,0,0.06)]">
            <div className="relative mx-auto mb-6 h-28 w-28">
              <div className="absolute inset-0 rotate-6 rounded-[1.75rem] bg-[#f3ecde]"></div>
              <div className="absolute inset-0 flex items-center justify-center rounded-[1.75rem] border border-black/10 bg-white shadow-[0_18px_40px_rgba(0,0,0,0.05)]">
                <Database className="h-10 w-10 text-[#2d8b69]" />
              </div>
            </div>

            <h3 className="mb-2 text-xl font-semibold text-gray-900">
              {dataSources.length === 0 ? 'Connect your first data source' : 'No results found'}
            </h3>
            <p className="mx-auto mb-6 max-w-md text-gray-600">
              {dataSources.length === 0
                ? 'Connect Slack, email, repositories, or other systems so your knowledge bases stay fresh and useful.'
                : 'Try adjusting your search or filters to find what you are looking for.'}
            </p>
            {dataSources.length === 0 && (
              <Link
                href="/data-sources/connect"
                className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
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
                className="group relative flex min-h-[292px] flex-col rounded-[1.7rem] border border-black/10 bg-white/80 shadow-[0_18px_40px_rgba(0,0,0,0.05)] transition-all hover:-translate-y-0.5 hover:border-black/15 hover:shadow-[0_22px_50px_rgba(0,0,0,0.08)]"
              >
                <div className="absolute right-4 top-4 z-20">
                  <button
                    type="button"
                    onClick={() => openDeleteModal(source)}
                    className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-red-200 bg-red-50/90 text-red-600 shadow-[0_8px_18px_rgba(0,0,0,0.06)] transition-colors hover:bg-red-100"
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
                        <h3 className="truncate text-[1.05rem] font-semibold text-gray-900">
                          {source.name || source.type?.toUpperCase() || 'UNKNOWN'}
                        </h3>
                        <p className="mt-1 text-sm font-medium text-[#2d8b69]">
                          {source.knowledge_base_name || `KB #${source.knowledge_base_id}`}
                        </p>
                      </div>
                    </div>
                    <span className="inline-flex items-center rounded-full bg-[#f1eadc] px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-[#6e675d]">
                      {source.type?.toUpperCase() || 'SOURCE'}
                    </span>
                  </div>

                  <div className="mb-4 flex flex-wrap items-center gap-2">
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${getStatusColor(source.status)}`}>
                      {getStatusIcon(source.status)}
                      {source.status?.toUpperCase()}
                    </span>
                    {WEBHOOK_SOURCES.includes(source.type?.toUpperCase()) && !source.config?.signing_secret && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-[#f8f0dd] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]">
                        <Webhook className="h-3 w-3" />
                        Setup needed
                      </span>
                    )}
                    {source.status?.toUpperCase() === 'SYNCING' && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-[#edf4f6] px-2.5 py-1 text-[11px] font-medium text-[#486c77]">
                        <Radio className="h-3 w-3" />
                        Live
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-3 gap-2.5">
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-3 py-3">
                      <div className="mb-1 flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5 text-gray-400" />
                        <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-gray-500">Documents</p>
                      </div>
                      <p className="text-base font-semibold text-gray-900">{source.total_documents}</p>
                    </div>
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-[#eef7f1] px-3 py-3">
                      <div className="mb-1 flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5 text-gray-400" />
                        <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-gray-500">Last Sync</p>
                      </div>
                      <p className="text-sm font-semibold text-gray-900">
                        {formatDate(source.last_sync_at)}
                      </p>
                    </div>
                    <div className="min-w-0 rounded-[1.15rem] border border-black/10 bg-[#f4efe4] px-3 py-3">
                      <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.1em] text-gray-500">Knowledge Base</div>
                      <p className="truncate text-sm font-semibold text-gray-900">
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
          <div className="w-full max-w-md rounded-[1.8rem] border border-black/10 bg-[#fcfaf5] p-6 shadow-[0_24px_70px_rgba(0,0,0,0.2)]">
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-[1rem] bg-red-50 p-2.5">
                <AlertCircle className="h-6 w-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Delete Data Source</h3>
            </div>

            <p className="mb-6 text-gray-600">
              Are you sure you want to delete the <span className="font-semibold">{deleteModal.source.name}</span> data source?
              This action cannot be undone and will permanently delete all associated documents.
            </p>

            <div className="flex justify-end gap-3">
              <button
                onClick={closeDeleteModal}
                disabled={deleting}
                className="rounded-[1rem] bg-[#f1eadc] px-4 py-2.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="flex items-center gap-2 rounded-[1rem] bg-red-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? (
                  <>
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
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
