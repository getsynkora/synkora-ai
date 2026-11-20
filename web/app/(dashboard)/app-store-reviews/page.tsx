'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  Smartphone,
  Plus,
  Trash2,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Clock,
  Search,
  Filter,
  Star,
  BarChart3,
  Settings
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface AppStoreSource {
  id: string
  knowledge_base_id: string
  knowledge_base_name?: string
  store_type: 'google_play' | 'apple_app_store'
  app_id: string
  app_name: string
  sync_frequency: string
  last_sync_at: string | null
  next_sync_at: string | null
  status: string
  total_reviews_collected: number
  created_at: string
  updated_at: string
}

export default function AppStoreReviewsPage() {
  const [sources, setSources] = useState<AppStoreSource[]>([])
  const [filteredSources, setFilteredSources] = useState<AppStoreSource[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterStore, setFilterStore] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [deleteModal, setDeleteModal] = useState<{ show: boolean; source: AppStoreSource | null }>({
    show: false,
    source: null,
  })
  const [deleting, setDeleting] = useState(false)
  const [syncing, setSyncing] = useState<string | null>(null)

  useEffect(() => {
    fetchSources()
  }, [])

  useEffect(() => {
    filterSources()
  }, [searchQuery, filterStore, filterStatus, sources])

  const fetchSources = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getAppStoreSources()
      setSources(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      toast.error('Failed to load app store sources')
    } finally {
      setLoading(false)
    }
  }

  const filterSources = () => {
    let filtered = sources

    if (searchQuery) {
      filtered = filtered.filter(source =>
        source.app_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        source.app_id?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    if (filterStore !== 'all') {
      filtered = filtered.filter(source => source.store_type === filterStore)
    }

    if (filterStatus !== 'all') {
      filtered = filtered.filter(source => source.status === filterStatus)
    }

    setFilteredSources(filtered)
  }

  const handleSync = async (sourceId: string) => {
    setSyncing(sourceId)
    try {
      await apiClient.syncAppStoreReviews(sourceId)
      toast.success('Review sync started successfully')
      fetchSources()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to sync reviews')
    } finally {
      setSyncing(null)
    }
  }

  const openDeleteModal = (source: AppStoreSource) => {
    setDeleteModal({ show: true, source })
  }

  const closeDeleteModal = () => {
    setDeleteModal({ show: false, source: null })
  }

  const confirmDelete = async () => {
    if (!deleteModal.source) return

    setDeleting(true)
    try {
      await apiClient.deleteAppStoreSource(deleteModal.source.id)
      toast.success('App store source deleted successfully')
      closeDeleteModal()
      fetchSources()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete source')
    } finally {
      setDeleting(false)
    }
  }

  const getStoreIcon = () => {
    return <Smartphone className="w-5 h-5" />
  }

  const getStoreColor = (storeType: string) => {
    switch (storeType) {
      case 'google_play':
        return 'bg-leaf-wash text-forest'
      case 'apple_app_store':
        return 'bg-sky-wash text-azure'
      default:
        return 'bg-sand text-ink'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'active':
        return 'bg-leaf-wash text-forest'
      case 'syncing':
        return 'bg-sky-wash text-azure'
      case 'paused':
        return 'bg-sand-deep text-gold'
      case 'error':
        return 'bg-blush-wash text-wine'
      default:
        return 'bg-sand text-ink'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'active':
        return <CheckCircle className="w-3 h-3" />
      case 'syncing':
        return <RefreshCw className="w-3 h-3 motion-safe:animate-spin" />
      case 'error':
        return <AlertCircle className="w-3 h-3" />
      default:
        return <Clock className="w-3 h-3" />
    }
  }

  const uniqueStores = Array.from(new Set(sources.map(s => s.store_type)))
  const uniqueStatuses = Array.from(new Set(sources.map(s => s.status)))

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-leaf"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">App Store Reviews</h1>
              <p className="text-ink-soft mt-2">
                Monitor and analyze reviews from Google Play and Apple App Store
              </p>
            </div>
            <Link
              href="/app-store-reviews/create"
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-leaf text-white rounded-lg hover:bg-forest transition-colors shadow-sm whitespace-nowrap"
            >
              <Plus className="w-5 h-5" />
              <span className="hidden sm:inline">Add App Source</span>
              <span className="sm:hidden">Add</span>
            </Link>
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6 mb-6">
            <div className="bg-white rounded-lg shadow-sm border border-line p-6">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-leaf-wash rounded-lg">
                  <Smartphone className="w-5 h-5 text-leaf" />
                </div>
                <p className="text-sm font-medium text-ink-soft">Total Apps</p>
              </div>
              <p className="text-xl sm:text-3xl font-bold text-ink">{sources.length}</p>
            </div>
            
            <div className="bg-white rounded-lg shadow-sm border border-line p-6">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-leaf-wash rounded-lg">
                  <CheckCircle className="w-5 h-5 text-leaf" />
                </div>
                <p className="text-sm font-medium text-ink-soft">Active</p>
              </div>
              <p className="text-xl sm:text-3xl font-bold text-ink">
                {sources.filter(s => s.status === 'active').length}
              </p>
            </div>
            
            <div className="bg-white rounded-lg shadow-sm border border-line p-6">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-sand-deep rounded-lg">
                  <Star className="w-5 h-5 text-plum" />
                </div>
                <p className="text-sm font-medium text-ink-soft">Total Reviews</p>
              </div>
              <p className="text-xl sm:text-3xl font-bold text-ink">
                {sources.reduce((sum, s) => sum + (s.total_reviews_collected || 0), 0).toLocaleString()}
              </p>
            </div>
            
            <div className="bg-white rounded-lg shadow-sm border border-line p-6">
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-leaf-wash rounded-lg">
                  <RefreshCw className="w-5 h-5 text-leaf" />
                </div>
                <p className="text-sm font-medium text-ink-soft">Syncing</p>
              </div>
              <p className="text-xl sm:text-3xl font-bold text-ink">
                {sources.filter(s => s.status === 'syncing').length}
              </p>
            </div>
          </div>

          {/* Search and Filter Bar */}
          <div className="bg-white rounded-lg shadow-sm border border-line p-4">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-ash" />
                <input
                  type="text"
                  placeholder="Search apps…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                />
              </div>
              <div className="flex items-center gap-2">
                <Filter className="w-5 h-5 text-ash" />
                <select
                  value={filterStore}
                  onChange={(e) => setFilterStore(e.target.value)}
                  className="px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                >
                  <option value="all">All Stores</option>
                  {uniqueStores.map(store => (
                    <option key={store} value={store}>
                      {store === 'google_play' ? 'Google Play' : 'App Store'}
                    </option>
                  ))}
                </select>
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-leaf focus:border-transparent"
                >
                  <option value="all">All Statuses</option>
                  {uniqueStatuses.map(status => (
                    <option key={status} value={status}>
                      {status}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 bg-sand-deep border-l-4 border-ink rounded-lg p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-danger" />
              <p className="text-danger">{error}</p>
            </div>
          </div>
        )}

        {/* Sources Grid */}
        {filteredSources.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border-2 border-dashed border-taupe p-12 text-center">
            <Smartphone className="w-16 h-16 text-ash mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-ink mb-2">
              {sources.length === 0 ? 'No app sources configured' : 'No results found'}
            </h3>
            <p className="text-ink-soft mb-6">
              {sources.length === 0
                ? 'Add your first app to start collecting and analyzing reviews.'
                : 'Try adjusting your search or filter criteria.'}
            </p>
            {sources.length === 0 && (
              <Link
                href="/app-store-reviews/create"
                className="inline-flex items-center gap-2 px-6 py-3 bg-leaf text-white rounded-lg hover:bg-forest transition-colors"
              >
                <Plus className="w-5 h-5" />
                Add App Source
              </Link>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredSources.map((source) => (
              <div
                key={source.id}
                className="bg-white rounded-lg shadow-sm border border-line hover:shadow-lg transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:border-mint"
              >
                <div className="p-6">
                  {/* Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-start gap-3 flex-1">
                      <div className={`p-2 rounded-lg ${getStoreColor(source.store_type)}`}>
                        {getStoreIcon()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="text-lg font-semibold text-ink mb-1 truncate">
                          {source.app_name}
                        </h3>
                        <p className="text-xs text-ink-mute truncate">{source.app_id}</p>
                        <Link
                          href={`/knowledge-bases/${source.knowledge_base_id}`}
                          className="text-sm text-leaf hover:text-forest truncate block mt-1"
                        >
                          {source.knowledge_base_name || `KB #${source.knowledge_base_id}`}
                        </Link>
                      </div>
                    </div>
                  </div>

                  {/* Store Type & Status */}
                  <div className="flex gap-2 mb-4">
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${getStoreColor(source.store_type)}`}>
                      {source.store_type === 'google_play' ? 'Google Play' : 'App Store'}
                    </span>
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${getStatusColor(source.status)}`}>
                      {getStatusIcon(source.status)}
                      {source.status}
                    </span>
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-2 gap-4 mb-4 py-4 border-t border-b border-sand">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <Star className="w-4 h-4 text-ash" />
                        <p className="text-xs text-ink-mute">Reviews</p>
                      </div>
                      <p className="text-xl font-bold text-ink">
                        {(source.total_reviews_collected || 0).toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <Clock className="w-4 h-4 text-ash" />
                        <p className="text-xs text-ink-mute">Last Sync</p>
                      </div>
                      <p className="text-xs text-ink">
                        {source.last_sync_at
                          ? new Date(source.last_sync_at).toLocaleDateString()
                          : 'Never'}
                      </p>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="grid grid-cols-2 gap-2">
                    <Link
                      href={`/app-store-reviews/${source.id}`}
                      className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-leaf bg-leaf-wash rounded-lg hover:bg-leaf-wash transition-colors"
                    >
                      <BarChart3 className="w-4 h-4" />
                      Insights
                    </Link>
                    <Link
                      href={`/app-store-reviews/${source.id}/edit`}
                      className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-ink-soft bg-cream rounded-lg hover:bg-sand transition-colors"
                    >
                      <Settings className="w-4 h-4" />
                      Edit
                    </Link>
                    <button
                      onClick={() => handleSync(source.id)}
                      disabled={syncing === source.id}
                      className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-leaf bg-leaf-wash rounded-lg hover:bg-leaf-wash transition-colors disabled:opacity-50"
                    >
                      <RefreshCw className={`w-4 h-4 ${syncing === source.id ? 'motion-safe:animate-spin' : ''}`} />
                      Sync
                    </button>
                    <button
                      onClick={() => openDeleteModal(source)}
                      className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-danger bg-blush-wash rounded-lg hover:bg-blush-wash transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {deleteModal.show && deleteModal.source && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-sand-deep rounded-lg">
                <AlertCircle className="w-6 h-6 text-danger" />
              </div>
              <h3 className="text-lg font-semibold text-ink">Delete App Source</h3>
            </div>
            
            <p className="text-ink-soft mb-6">
              Are you sure you want to delete <span className="font-semibold">{deleteModal.source.app_name}</span>? 
              This will stop collecting reviews and remove all associated data.
            </p>
            
            <div className="flex gap-3 justify-end">
              <button
                onClick={closeDeleteModal}
                disabled={deleting}
                className="px-4 py-2 text-sm font-medium text-ink-soft bg-sand rounded-lg hover:bg-line transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="px-4 py-2 text-sm font-medium text-white bg-danger rounded-lg hover:bg-danger transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {deleting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full motion-safe:animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
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
