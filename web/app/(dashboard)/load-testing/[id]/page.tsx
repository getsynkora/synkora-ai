'use client'

import { useState, useEffect, use } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import {
  ArrowLeft,
  Play,
  Edit,
  Trash2,
  Clock,
  Server,
  Activity,
  Settings,
  BarChart3,
  Code,
  Eye,
  Plus,
  CheckCircle,
  AlertCircle,
  XCircle,
} from 'lucide-react'
import {
  getLoadTest,
  getTestScenarios,
  getTestRuns,
  startTestRun,
  updateLoadTest,
  deleteLoadTest,
  type LoadTest,
  type TestScenario,
  type TestRun,
} from '@/lib/api/load-testing'

export default function LoadTestDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const [loadTest, setLoadTest] = useState<LoadTest | null>(null)
  const [scenarios, setScenarios] = useState<TestScenario[]>([])
  const [testRuns, setTestRuns] = useState<TestRun[]>([])
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [deleteModal, setDeleteModal] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showScript, setShowScript] = useState(false)

  useEffect(() => {
    fetchData()
  }, [id])

  const fetchData = async () => {
    try {
      setLoading(true)
      const [testData, scenariosData, runsData] = await Promise.all([
        getLoadTest(id),
        getTestScenarios(id),
        getTestRuns({ load_test_id: id, page_size: 5 }),
      ])
      setLoadTest(testData)
      setScenarios(scenariosData)
      setTestRuns(runsData.items || [])
    } catch (err) {
      toast.error('Failed to load test details')
    } finally {
      setLoading(false)
    }
  }

  const handleStartTest = async () => {
    if (!loadTest) return

    setStarting(true)
    try {
      const run = await startTestRun(loadTest.id)
      toast.success('Test run started!')
      router.push(`/load-testing/${id}/runs/${run.id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start test')
    } finally {
      setStarting(false)
    }
  }

  const handleMarkReady = async () => {
    if (!loadTest) return

    try {
      await updateLoadTest(id, { status: 'ready' })
      setLoadTest({ ...loadTest, status: 'ready' })
      toast.success('Test marked as ready')
    } catch (err) {
      toast.error('Failed to update status')
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await deleteLoadTest(id)
      toast.success('Load test deleted')
      router.push('/load-testing')
    } catch (err) {
      toast.error('Failed to delete load test')
    } finally {
      setDeleting(false)
    }
  }

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      draft: 'bg-gray-100 text-gray-700',
      ready: 'bg-blue-100 text-blue-700',
      running: 'bg-green-100 text-green-700',
      paused: 'bg-yellow-100 text-yellow-700',
      completed: 'bg-emerald-100 text-emerald-700',
      failed: 'bg-red-100 text-red-700',
      cancelled: 'bg-gray-100 text-gray-700',
      pending: 'bg-blue-100 text-blue-700',
      initializing: 'bg-yellow-100 text-yellow-700',
    }
    return styles[status] || styles.draft
  }

  const getRunIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-emerald-600" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-600" />
      case 'cancelled':
        return <XCircle className="w-4 h-4 text-gray-600" />
      case 'running':
      case 'initializing':
        return <Activity className="w-4 h-4 text-green-600 animate-pulse" />
      default:
        return <Clock className="w-4 h-4 text-blue-600" />
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-'
    if (seconds < 60) return `${seconds.toFixed(1)}s`
    const mins = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return `${mins}m ${secs}s`
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-slate-50 via-white to-primary-50/30">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading test details...</p>
        </div>
      </div>
    )
  }

  if (!loadTest) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-primary-50/30 p-4 md:p-6">
        <div className="max-w-4xl mx-auto text-center py-12">
          <AlertCircle className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Test Not Found</h2>
          <Link href="/load-testing" className="text-primary-600 hover:text-primary-700">
            Back to Load Tests
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-primary-50/30 p-4 md:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/load-testing"
            className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Load Tests
          </Link>

          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">{loadTest.name}</h1>
                <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${getStatusBadge(loadTest.status)}`}>
                  {loadTest.status.charAt(0).toUpperCase() + loadTest.status.slice(1)}
                </span>
              </div>
              <p className="text-gray-600">{loadTest.description || 'No description'}</p>
            </div>

            <div className="flex gap-3 flex-wrap">
              {loadTest.status === 'draft' && (
                <button
                  onClick={handleMarkReady}
                  className="inline-flex items-center gap-2 px-4 py-2.5 border border-blue-200 bg-blue-50 text-blue-700 rounded-xl hover:bg-blue-100 transition-colors font-medium"
                >
                  <CheckCircle className="w-4 h-4" />
                  Mark Ready
                </button>
              )}
              {loadTest.status === 'ready' && (
                <button
                  onClick={handleStartTest}
                  disabled={starting}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white rounded-xl transition-all shadow-sm hover:shadow-md font-medium disabled:opacity-50"
                >
                  {starting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Starting...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      Run Test
                    </>
                  )}
                </button>
              )}
              <Link
                href={`/load-testing/${id}/runs`}
                className="inline-flex items-center gap-2 px-4 py-2.5 border border-gray-200 bg-white text-gray-700 rounded-xl hover:bg-gray-50 transition-colors font-medium"
              >
                <BarChart3 className="w-4 h-4" />
                All Runs
              </Link>
              <button
                onClick={() => setDeleteModal(true)}
                disabled={loadTest.status === 'running'}
                className="inline-flex items-center gap-2 px-4 py-2.5 border border-red-200 bg-red-50 text-red-600 rounded-xl hover:bg-red-100 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Target Config */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Server className="w-5 h-5 text-primary-600" />
                Target Configuration
              </h2>

              <div className="space-y-3">
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-600">Target URL</span>
                  <span className="text-gray-900 font-mono text-sm truncate max-w-xs">
                    {loadTest.target_url}
                  </span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-600">API Type</span>
                  <span className="text-gray-900">{loadTest.target_type}</span>
                </div>
                {loadTest.proxy_config_id && (
                  <div className="flex justify-between py-2 border-b border-gray-100">
                    <span className="text-gray-600">Using Mock Proxy</span>
                    <span className="text-green-600">Yes</span>
                  </div>
                )}
              </div>
            </div>

            {/* Load Config */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5 text-primary-600" />
                Load Configuration
              </h2>

              <div className="space-y-4">
                {/* Stages */}
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Load Stages</h3>
                  <div className="flex flex-wrap gap-2">
                    {(loadTest.load_config?.stages || []).map((stage: any, i: number) => (
                      <div
                        key={i}
                        className="px-3 py-1.5 bg-primary-50 text-primary-700 rounded-lg text-sm"
                      >
                        {stage.duration} → {stage.target} VUs
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div className="p-3 bg-gray-50 rounded-lg">
                    <div className="text-sm text-gray-500">Max VUs</div>
                    <div className="text-lg font-semibold text-gray-900">
                      {loadTest.load_config?.max_vus || 100}
                    </div>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg">
                    <div className="text-sm text-gray-500">Think Time Min</div>
                    <div className="text-lg font-semibold text-gray-900">
                      {loadTest.load_config?.think_time_min_ms || 1000}ms
                    </div>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg">
                    <div className="text-sm text-gray-500">Think Time Max</div>
                    <div className="text-lg font-semibold text-gray-900">
                      {loadTest.load_config?.think_time_max_ms || 3000}ms
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Scenarios */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Code className="w-5 h-5 text-primary-600" />
                  Test Scenarios
                </h2>
                <Link
                  href={`/load-testing/${id}/scenarios/create`}
                  className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
                >
                  <Plus className="w-4 h-4" />
                  Add Scenario
                </Link>
              </div>

              {scenarios.length === 0 ? (
                <p className="text-gray-500 text-center py-8">
                  No scenarios configured. Add scenarios to customize test prompts.
                </p>
              ) : (
                <div className="space-y-3">
                  {scenarios.map((scenario) => (
                    <div
                      key={scenario.id}
                      className="p-4 border border-gray-100 rounded-lg hover:border-primary-200 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-medium text-gray-900">{scenario.name}</h3>
                          <p className="text-sm text-gray-500">{scenario.description || 'No description'}</p>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="px-2 py-1 bg-primary-50 text-primary-700 rounded text-sm">
                            Weight: {scenario.weight}
                          </span>
                          <span className="text-sm text-gray-500">
                            {scenario.prompts.length} prompt(s)
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Recent Runs */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Clock className="w-5 h-5 text-primary-600" />
                Recent Runs
              </h2>

              {testRuns.length === 0 ? (
                <p className="text-gray-500 text-center py-4">No test runs yet</p>
              ) : (
                <div className="space-y-3">
                  {testRuns.map((run) => (
                    <Link
                      key={run.id}
                      href={`/load-testing/${id}/runs/${run.id}`}
                      className="block p-3 border border-gray-100 rounded-lg hover:border-primary-200 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {getRunIcon(run.status)}
                          <span className={`text-sm font-medium ${getStatusBadge(run.status).replace('bg-', 'text-').replace('-100', '-700')}`}>
                            {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
                          </span>
                        </div>
                        <span className="text-xs text-gray-500">
                          {formatDuration(run.duration_seconds)}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500">
                        {run.started_at ? formatDate(run.started_at) : 'Pending'}
                      </div>
                      {run.summary_metrics && (
                        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <span className="text-gray-500">Requests:</span>{' '}
                            <span className="font-medium">{run.total_requests || 0}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Peak VUs:</span>{' '}
                            <span className="font-medium">{run.peak_vus || 0}</span>
                          </div>
                        </div>
                      )}
                    </Link>
                  ))}
                </div>
              )}

              <Link
                href={`/load-testing/${id}/runs`}
                className="block mt-4 text-center text-sm text-primary-600 hover:text-primary-700"
              >
                View all runs →
              </Link>
            </div>

            {/* Quick Stats */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Info</h2>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-500">Created</span>
                  <span className="text-gray-900 text-sm">
                    {new Date(loadTest.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Updated</span>
                  <span className="text-gray-900 text-sm">
                    {new Date(loadTest.updated_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Total Runs</span>
                  <span className="text-gray-900 font-medium">{testRuns.length}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Delete Modal */}
      {deleteModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 bg-red-100 rounded-xl">
                <Trash2 className="w-6 h-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Delete Load Test</h3>
            </div>

            <p className="text-gray-600 mb-6">
              Are you sure you want to delete <span className="font-semibold text-gray-900">"{loadTest.name}"</span>?
              All test runs and results will be permanently removed.
            </p>

            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteModal(false)}
                disabled={deleting}
                className="px-4 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {deleting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
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
