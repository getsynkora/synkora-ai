'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { listDebates, deleteDebate } from '@/lib/api/war-room'
import type { DebateListItem } from '@/lib/api/war-room'
import {
  Swords,
  Plus,
  Trash2,
  Edit,
  Search,
  Filter,
  AlertCircle,
  Users,
  CheckCircle,
  Play,
  Globe,
  Clock,
  Pause,
  Zap,
  Eye,
} from 'lucide-react'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

const STATUS_CONFIG: Record<string, { label: string; className: string; icon: React.ReactNode }> = {
  pending: {
    label: 'Pending',
    className: 'bg-sand text-ink',
    icon: <Clock className="w-3 h-3" />,
  },
  active: {
    label: 'Live',
    className: 'bg-leaf-wash text-forest',
    icon: <Play className="w-3 h-3" />,
  },
  synthesizing: {
    label: 'Synthesizing',
    className: 'bg-sand-deep text-gold',
    icon: <Zap className="w-3 h-3" />,
  },
  completed: {
    label: 'Completed',
    className: 'bg-sky-wash text-azure',
    icon: <CheckCircle className="w-3 h-3" />,
  },
  error: {
    label: 'Error',
    className: 'bg-blush-wash text-wine',
    icon: <AlertCircle className="w-3 h-3" />,
  },
}

export default function WarRoomPage() {
  const router = useRouter()
  const [debates, setDebates] = useState<DebateListItem[]>([])
  const [filteredDebates, setFilteredDebates] = useState<DebateListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [filterType, setFilterType] = useState<string>('all')
  const [deleteModal, setDeleteModal] = useState<{ show: boolean; debate: DebateListItem | null }>({
    show: false,
    debate: null,
  })
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    loadDebates()
  }, [])

  useEffect(() => {
    filterDebates()
  }, [searchQuery, filterStatus, filterType, debates])

  const loadDebates = async () => {
    try {
      setLoading(true)
      const data = await listDebates()
      setDebates(data.debates || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      console.error('Failed to load debates:', err)
    } finally {
      setLoading(false)
    }
  }

  const filterDebates = () => {
    let filtered = debates

    if (searchQuery) {
      filtered = filtered.filter((debate) =>
        debate.topic?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    if (filterStatus !== 'all') {
      filtered = filtered.filter((debate) => debate.status === filterStatus)
    }

    if (filterType !== 'all') {
      filtered = filtered.filter((debate) => debate.debate_type === filterType)
    }

    setFilteredDebates(filtered)
  }

  const handleDelete = async (debate: DebateListItem, e: React.MouseEvent) => {
    e.stopPropagation()
    setDeleteModal({ show: true, debate })
  }

  const confirmDelete = async () => {
    if (!deleteModal.debate) return

    setDeleting(true)
    try {
      await deleteDebate(deleteModal.debate.id)
      setDebates((prev) => prev.filter((d) => d.id !== deleteModal.debate!.id))
      setDeleteModal({ show: false, debate: null })
    } catch (err) {
      console.error('Failed to delete:', err)
    } finally {
      setDeleting(false)
    }
  }

  const uniqueStatuses = Array.from(new Set(debates.map((d) => d.status)))
  const uniqueTypes = Array.from(new Set(debates.map((d) => d.debate_type)))

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-danger"></div>
      </div>
    )
  }

  return (
    <DashboardPageShell
      title="AI War Room"
      description="Multi-agent debates and discussions."
      icon={Swords}
      badge="Labs"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'War Room' },
      ]}
      actions={
        <button
          onClick={() => router.push('/war-room/create')}
          className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
        >
          <Plus className="h-4 w-4" />
          New Debate
        </button>
      }
      stats={[
        { label: 'Total', value: debates.length },
        { label: 'Active', value: debates.filter((d) => d.status === 'active').length },
      ]}
    >
        {/* Header */}
        <div className="mb-6">
          {/* Stats Bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 mb-4 md:mb-5">
            <div className="bg-white rounded-lg shadow-sm border border-line p-4">
              <div className="flex items-center gap-2 mb-1">
                <div className="p-1.5 bg-blush-wash rounded-lg">
                  <Swords className="w-4 h-4 text-leaf" />
                </div>
                <p className="text-xs font-medium text-ink-soft">Total</p>
              </div>
              <p className="text-2xl font-bold text-ink">{debates.length}</p>
            </div>

            <div className="bg-white rounded-lg shadow-sm border border-line p-4">
              <div className="flex items-center gap-2 mb-1">
                <div className="p-1.5 bg-leaf-wash rounded-lg">
                  <Play className="w-4 h-4 text-leaf" />
                </div>
                <p className="text-xs font-medium text-ink-soft">Active</p>
              </div>
              <p className="text-2xl font-bold text-ink">
                {debates.filter((d) => d.status === 'active').length}
              </p>
            </div>

            <div className="bg-white rounded-lg shadow-sm border border-line p-4">
              <div className="flex items-center gap-2 mb-1">
                <div className="p-1.5 bg-sky-wash rounded-lg">
                  <CheckCircle className="w-4 h-4 text-azure" />
                </div>
                <p className="text-xs font-medium text-ink-soft">Completed</p>
              </div>
              <p className="text-2xl font-bold text-ink">
                {debates.filter((d) => d.status === 'completed').length}
              </p>
            </div>

            <div className="bg-white rounded-lg shadow-sm border border-line p-4">
              <div className="flex items-center gap-2 mb-1">
                <div className="p-1.5 bg-blush-wash rounded-lg">
                  <Globe className="w-4 h-4 text-plum" />
                </div>
                <p className="text-xs font-medium text-ink-soft">Public</p>
              </div>
              <p className="text-2xl font-bold text-ink">
                {debates.filter((d) => d.is_public).length}
              </p>
            </div>
          </div>

          {/* Search and Filter Bar */}
          <DashboardPagePanel className="p-3">
            <div className="flex flex-col md:flex-row gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-ash" />
                <input
                  type="text"
                  placeholder="Search debates…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-[1rem] border border-black/10 bg-cream py-3 pl-10 pr-4 text-sm text-ink placeholder-ash focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint"
                />
              </div>
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-ash" />
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="rounded-[1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint"
                >
                  <option value="all">All Status</option>
                  {uniqueStatuses.map((status) => (
                    <option key={status} value={status}>
                      {STATUS_CONFIG[status]?.label || status}
                    </option>
                  ))}
                </select>
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  className="rounded-[1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint"
                >
                  <option value="all">All Types</option>
                  {uniqueTypes.map((type) => (
                    <option key={type} value={type} className="capitalize">
                      {type}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </DashboardPagePanel>
        </div>

        {/* Error Message */}
        {error && (
          <DashboardPagePanel className="mb-6 border-blush-wash bg-white p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-wine" />
              <p className="text-wine">{error}</p>
            </div>
          </DashboardPagePanel>
        )}

        {/* Debates Grid */}
        {filteredDebates.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border-2 border-dashed border-taupe p-10 text-center">
            <Swords className="w-12 h-12 text-ash mx-auto mb-3" />
            <h3 className="text-base font-semibold text-ink mb-2">
              {debates.length === 0 ? 'No debates yet' : 'No results found'}
            </h3>
            <p className="text-sm text-ink-soft mb-5">
              {debates.length === 0
                ? 'Create your first AI debate. Pick a topic, select agents, and watch them argue it out.'
                : 'Try adjusting your search or filter criteria.'}
            </p>
            {debates.length === 0 && (
              <button
                onClick={() => router.push('/war-room/create')}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-ink hover:bg-ink/85 text-white rounded-lg transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm hover:shadow-md text-sm font-medium"
              >
                <Plus className="w-4 h-4" />
                Create First Debate
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredDebates.map((debate) => {
              const statusInfo = STATUS_CONFIG[debate.status] || STATUS_CONFIG.pending
              return (
                <div
                  key={debate.id}
                  onClick={() => router.push(`/war-room/${debate.id}`)}
                  className="bg-white rounded-lg shadow-sm border border-line hover:shadow-md transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:border-blush cursor-pointer"
                >
                  <div className="p-4">
                    {/* Header */}
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-start gap-2.5 flex-1 min-w-0">
                        <div className="p-1.5 rounded-lg flex-shrink-0 bg-blush-wash text-wine">
                          <Swords className="w-4 h-4" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3
                            className="text-base font-semibold text-ink mb-0.5 break-words line-clamp-2"
                            title={debate.topic}
                          >
                            {debate.topic}
                          </h3>
                          <p className="text-xs text-ink-mute flex items-center gap-1 flex-wrap">
                            <Users className="w-3 h-3 flex-shrink-0" />
                            <span>{debate.participant_count} agents</span>
                            <span className="mx-1">-</span>
                            <span className="capitalize">{debate.debate_type}</span>
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Status Badge */}
                    <div className="mb-3 flex items-center gap-2">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusInfo.className}`}
                      >
                        {statusInfo.icon}
                        {debate.status === 'active' && (
                          <span className="w-1.5 h-1.5 rounded-full bg-leaf motion-safe:animate-pulse" />
                        )}
                        {statusInfo.label}
                      </span>
                      {debate.is_public && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blush-wash text-wine">
                          <Globe className="w-3 h-3" />
                          Public
                        </span>
                      )}
                    </div>

                    {/* Round Info */}
                    <div className="text-xs text-ink-mute mb-3 space-y-0.5 p-2.5 bg-cream rounded-lg">
                      <p>
                        Round {debate.current_round}/{debate.rounds}
                      </p>
                      <p className="capitalize">Type: {debate.debate_type}</p>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-1.5 flex-wrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          router.push(`/war-room/${debate.id}`)
                        }}
                        className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium text-leaf bg-blush-wash rounded-lg hover:bg-blush-wash transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        View
                      </button>
                      {debate.status === 'pending' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            router.push(`/war-room/create?edit=${debate.id}`)
                          }}
                          className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-medium text-ink-soft bg-sand rounded-lg hover:bg-line transition-colors"
                        >
                          <Edit className="w-3.5 h-3.5" />
                        </button>
                      )}
                      <button
                        onClick={(e) => handleDelete(debate, e)}
                        className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-medium text-danger bg-blush-wash rounded-lg hover:bg-blush-wash transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      {/* Delete Confirmation Modal */}
      {deleteModal.show && deleteModal.debate && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-md rounded-[1.9rem] border border-line bg-white p-6 shadow-soft">
            <div className="flex items-center gap-3 mb-4">
              <div className="rounded-lg bg-cream p-2">
                <AlertCircle className="w-6 h-6 text-wine" />
              </div>
              <h3 className="text-lg font-semibold text-ink">Delete Debate</h3>
            </div>

            <p className="text-sm text-ink-soft mb-6">
              Are you sure you want to delete{' '}
              <span className="font-semibold">"{deleteModal.debate.topic}"</span>? This action
              cannot be undone and will permanently remove this debate.
            </p>

            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteModal({ show: false, debate: null })}
                disabled={deleting}
                className="rounded-[0.95rem] bg-sand-deep px-4 py-2 text-sm font-semibold text-ink transition-colors hover:bg-line disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="flex items-center gap-2 rounded-[0.95rem] bg-ink px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
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
    </DashboardPageShell>
  )
}
