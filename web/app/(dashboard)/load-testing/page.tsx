'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  Activity,
  Plus,
  Edit,
  Trash2,
  Play,
  Eye,
  Search,
  Clock,
  CheckCircle,
  AlertCircle,
  Zap,
  Server,
  BarChart3,
  Settings,
} from 'lucide-react'
import {
  getLoadTests,
  deleteLoadTest,
  type LoadTest,
} from '@/lib/api/load-testing'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

export default function LoadTestingPage() {
  const [loadTests, setLoadTests] = useState<LoadTest[]>([])
  const [filteredTests, setFilteredTests] = useState<LoadTest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [deleteModal, setDeleteModal] = useState<{ show: boolean; test: LoadTest | null }>({
    show: false,
    test: null,
  })
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    fetchLoadTests()
  }, [])

  useEffect(() => {
    filterTests()
  }, [searchQuery, statusFilter, loadTests])

  const fetchLoadTests = async () => {
    try {
      setLoading(true)
      const response = await getLoadTests()
      setLoadTests(response.items || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tests')
      toast.error('Failed to load load tests')
    } finally {
      setLoading(false)
    }
  }

  const filterTests = () => {
    let filtered = loadTests

    if (searchQuery) {
      filtered = filtered.filter(test =>
        test.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        test.description?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    if (statusFilter) {
      filtered = filtered.filter(test => test.status === statusFilter)
    }

    setFilteredTests(filtered)
  }

  const openDeleteModal = (test: LoadTest) => {
    setDeleteModal({ show: true, test })
  }

  const closeDeleteModal = () => {
    setDeleteModal({ show: false, test: null })
  }

  const confirmDelete = async () => {
    if (!deleteModal.test) return

    setDeleting(true)
    try {
      await deleteLoadTest(deleteModal.test.id)
      toast.success(`"${deleteModal.test.name}" has been deleted`)
      closeDeleteModal()
      fetchLoadTests()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete')
    } finally {
      setDeleting(false)
    }
  }

  const getStatusBadge = (status: string) => {
    const styles = {
      draft: 'bg-sand text-ink-soft',
      ready: 'bg-sky-wash text-azure',
      running: 'bg-leaf-wash text-forest',
      paused: 'bg-sand-deep text-gold',
    }
    return styles[status as keyof typeof styles] || styles.draft
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-cream50/30">
        <div className="text-center">
          <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-ink-soft">Loading your load tests…</p>
        </div>
      </div>
    )
  }

  return (
    <DashboardPageShell
      title="Load Testing"
      description="Test your AI agents at scale with K6-powered load tests."
      icon={Activity}
      badge="Labs"
      maxWidthClassName="max-w-6xl"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Load Testing' },
      ]}
      actions={
        <div className="flex flex-wrap gap-3">
          <Link
            href="/load-testing/proxy"
            className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-white/85 px-4 py-3 text-sm font-semibold text-ink-soft transition-colors hover:bg-white hover:text-ink"
          >
            <Server className="h-4 w-4" />
            Proxy Config
          </Link>
          <Link
            href="/load-testing/create"
            className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
          >
            <Plus className="h-4 w-4" />
            Create Test
          </Link>
        </div>
      }
      stats={[
        { label: 'Total', value: loadTests.length },
        { label: 'Running', value: loadTests.filter(t => t.status === 'running').length },
      ]}
    >
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        {[
          { label: 'Total Tests', value: loadTests.length, icon: Activity, tone: 'bg-sky-wash text-azure' },
          { label: 'Running', value: loadTests.filter(t => t.status === 'running').length, icon: Zap, tone: 'bg-leaf-wash text-forest' },
          { label: 'Ready', value: loadTests.filter(t => t.status === 'ready').length, icon: CheckCircle, tone: 'bg-leaf-wash text-forest' },
          { label: 'Draft', value: loadTests.filter(t => t.status === 'draft').length, icon: Edit, tone: 'bg-sand text-bark' },
        ].map((stat) => (
          <DashboardPagePanel key={stat.label} className="p-5">
            <div className="flex items-center gap-3">
              <div className={`rounded-[1rem] p-2.5 ${stat.tone}`}>
                <stat.icon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-ink-soft">{stat.label}</p>
                <p className="text-2xl font-semibold tracking-[-0.04em] text-ink">{stat.value}</p>
              </div>
            </div>
          </DashboardPagePanel>
        ))}
      </div>

      {loadTests.length > 0 ? (
        <DashboardPagePanel className="bg-cream mb-6 p-4">
          <div className="flex flex-col gap-4 md:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ash" />
              <input
                type="text"
                placeholder="Search load tests…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-[1rem] border border-black/10 bg-cream py-3 pl-11 pr-4 text-sm text-ink placeholder-ash focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-[1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint"
            >
              <option value="">All Status</option>
              <option value="draft">Draft</option>
              <option value="ready">Ready</option>
              <option value="running">Running</option>
            </select>
          </div>
        </DashboardPagePanel>
      ) : null}

        {/* Error Message */}
        {error && (
          <DashboardPagePanel className="mb-6 border-blush-wash bg-white p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-wine" />
              <p className="text-wine">{error}</p>
            </div>
          </DashboardPagePanel>
        )}

        {/* Load Tests Grid */}
        {filteredTests.length === 0 ? (
          <DashboardPagePanel className="p-12 text-center">
            <div className="w-32 h-32 mx-auto mb-6 relative">
              <div className="absolute inset-0 rounded-2xl bg-sand transform rotate-6"></div>
              <div className="absolute inset-0 flex items-center justify-center rounded-2xl border border-sand bg-white shadow-sm">
                <BarChart3 className="w-12 h-12 text-ink" />
              </div>
            </div>

            <h3 className="text-xl font-semibold text-ink mb-2">
              {loadTests.length === 0 ? 'Create your first load test' : 'No results found'}
            </h3>
            <p className="text-ink-soft mb-6 max-w-md mx-auto">
              {loadTests.length === 0
                ? 'Load tests help you understand how your AI agents perform under heavy traffic.'
                : 'Try adjusting your search or filters.'}
            </p>
            {loadTests.length === 0 && (
              <Link
                href="/load-testing/create"
                className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-6 py-3 font-semibold text-white transition-colors hover:bg-black"
              >
                <Plus className="w-5 h-5" />
                Create Load Test
              </Link>
            )}
          </DashboardPagePanel>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredTests.map((test) => (
              <DashboardPagePanel
                key={test.id}
                className="group p-5 transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:-translate-y-0.5 hover:border-tan"
              >
                  {/* Header */}
                  <div className="flex items-start gap-3 mb-4">
                    <div className="rounded-xl bg-sand p-2.5 transition-colors group-hover:bg-line">
                      <Activity className="w-5 h-5 text-ink" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold text-ink truncate">
                        {test.name}
                      </h3>
                      <p className="text-sm text-ink-mute line-clamp-2 mt-1">
                        {test.description || 'No description'}
                      </p>
                    </div>
                  </div>

                  {/* Status Badge */}
                  <div className="mb-4">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${getStatusBadge(test.status)}`}>
                      <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                      {test.status.charAt(0).toUpperCase() + test.status.slice(1)}
                    </span>
                  </div>

                  {/* Info */}
                  <div className="flex items-center gap-4 mb-4 py-3 border-t border-sand">
                    <div className="flex items-center gap-2">
                      <Server className="w-4 h-4 text-ash" />
                      <span className="text-sm text-ink-soft truncate max-w-[150px]">
                        {test.target_type}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-ash" />
                      <span className="text-sm text-ink-mute">{formatDate(test.updated_at)}</span>
                    </div>
                  </div>

                  {/* Last Run */}
                  {test.last_run && (
                    <div className="mb-4 p-3 bg-cream rounded-lg">
                      <div className="text-xs text-ink-mute mb-1">Last Run</div>
                      <div className="flex items-center justify-between">
                        <span className={`text-sm font-medium ${
                          test.last_run.status === 'completed' ? 'text-leaf' :
                          test.last_run.status === 'failed' ? 'text-danger' :
                          'text-ink-soft'
                        }`}>
                          {test.last_run.status.charAt(0).toUpperCase() + test.last_run.status.slice(1)}
                        </span>
                        {test.last_run.started_at && (
                          <span className="text-xs text-ink-mute">
                            {formatDate(test.last_run.started_at)}
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2">
                    <Link
                      href={`/load-testing/${test.id}`}
                      className="flex-1 inline-flex items-center justify-center gap-2 rounded-[0.95rem] bg-ink px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black"
                    >
                      <Eye className="w-4 h-4" />
                      View
                    </Link>
                    {test.status === 'ready' && (
                      <Link
                        href={`/load-testing/${test.id}/runs`}
                        className="inline-flex items-center justify-center rounded-[0.95rem] bg-leaf-wash px-3 py-2.5 text-sm font-semibold text-forest transition-colors hover:bg-leaf-wash"
                      >
                        <Play className="w-4 h-4" />
                      </Link>
                    )}
                    <button
                      onClick={() => openDeleteModal(test)}
                      disabled={test.status === 'running'}
                      className="inline-flex items-center justify-center rounded-[0.95rem] bg-cream px-3 py-2.5 text-sm font-semibold text-wine transition-colors hover:bg-blush-wash disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
              </DashboardPagePanel>
            ))}
          </div>
        )}

      {/* Delete Modal */}
      {deleteModal.show && deleteModal.test && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-md rounded-[1.9rem] border border-line bg-white p-6 shadow-soft">
            <div className="flex items-center gap-3 mb-4">
              <div className="rounded-xl bg-cream p-2.5">
                <Trash2 className="w-6 h-6 text-wine" />
              </div>
              <h3 className="text-lg font-semibold text-ink">Delete Load Test</h3>
            </div>

            <p className="text-ink-soft mb-6">
              Are you sure you want to delete <span className="font-semibold text-ink">"{deleteModal.test.name}"</span>?
              All test runs and results will be permanently removed.
            </p>

            <div className="flex gap-3 justify-end">
              <button
                onClick={closeDeleteModal}
                disabled={deleting}
                className="rounded-[0.95rem] bg-sand-deep px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-line disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="flex items-center gap-2 rounded-[0.95rem] bg-ink px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
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
