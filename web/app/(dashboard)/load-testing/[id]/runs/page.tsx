'use client'

import { useState, useEffect, use } from 'react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  ArrowLeft,
  Play,
  Clock,
  Activity,
  CheckCircle,
  XCircle,
  AlertCircle,
  BarChart3,
  RefreshCw,
  Filter,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import {
  getLoadTest,
  getTestRuns,
  startTestRun,
  type LoadTest,
  type TestRun,
} from '@/lib/api/load-testing'

export default function TestRunsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [loadTest, setLoadTest] = useState<LoadTest | null>(null)
  const [testRuns, setTestRuns] = useState<TestRun[]>([])
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const pageSize = 10

  useEffect(() => {
    fetchData()
  }, [id, page, statusFilter])

  const fetchData = async () => {
    try {
      setLoading(true)
      const [testData, runsData] = await Promise.all([
        getLoadTest(id),
        getTestRuns({
          load_test_id: id,
          page,
          page_size: pageSize,
          status: statusFilter || undefined,
        }),
      ])
      setLoadTest(testData)
      setTestRuns(runsData.items || [])
      setTotal(runsData.total || 0)
    } catch (err) {
      toast.error('Failed to load test runs')
    } finally {
      setLoading(false)
    }
  }

  const handleStartTest = async () => {
    if (!loadTest || loadTest.status !== 'ready') return

    setStarting(true)
    try {
      const run = await startTestRun(loadTest.id)
      toast.success('Test run started!')
      // Refresh the list
      fetchData()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start test')
    } finally {
      setStarting(false)
    }
  }

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      pending: 'bg-blue-100 text-blue-700',
      initializing: 'bg-yellow-100 text-yellow-700',
      running: 'bg-green-100 text-green-700',
      stopping: 'bg-orange-100 text-orange-700',
      completed: 'bg-emerald-100 text-emerald-700',
      failed: 'bg-red-100 text-red-700',
      cancelled: 'bg-gray-100 text-gray-700',
    }
    return styles[status] || styles.pending
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-emerald-600" />
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-600" />
      case 'cancelled':
        return <XCircle className="w-5 h-5 text-gray-600" />
      case 'running':
      case 'initializing':
        return <Activity className="w-5 h-5 text-green-600 animate-pulse" />
      default:
        return <Clock className="w-5 h-5 text-blue-600" />
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleString()
  }

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-'
    if (seconds < 60) return `${seconds.toFixed(1)}s`
    const mins = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return `${mins}m ${secs}s`
  }

  const totalPages = Math.ceil(total / pageSize)

  if (loading && !loadTest) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-slate-50 via-white to-primary-50/30">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading test runs...</p>
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
            href={`/load-testing/${id}`}
            className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to {loadTest.name}
          </Link>

          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Test Runs</h1>
              <p className="text-gray-600 mt-1">
                View all test runs for {loadTest.name}
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={fetchData}
                className="inline-flex items-center gap-2 px-4 py-2.5 border border-gray-200 bg-white text-gray-700 rounded-xl hover:bg-gray-50 transition-colors font-medium"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
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
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-6 flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-500" />
            <span className="text-sm text-gray-600">Filter:</span>
          </div>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value)
              setPage(1)
            }}
            className="px-4 py-2 bg-white border border-gray-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent shadow-sm"
          >
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="initializing">Initializing</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <span className="text-sm text-gray-500">
            {total} total run{total !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Test Runs List */}
        {testRuns.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-12 text-center">
            <div className="w-32 h-32 mx-auto mb-6 relative">
              <div className="absolute inset-0 bg-gradient-to-br from-primary-100 to-primary-50 rounded-2xl transform rotate-6"></div>
              <div className="absolute inset-0 bg-white rounded-2xl shadow-sm border border-gray-100 flex items-center justify-center">
                <BarChart3 className="w-12 h-12 text-primary-500" />
              </div>
            </div>

            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              {statusFilter ? 'No runs match filter' : 'No test runs yet'}
            </h3>
            <p className="text-gray-600 mb-6 max-w-md mx-auto">
              {statusFilter
                ? 'Try changing your filter settings.'
                : 'Start a test run to see performance metrics and results here.'}
            </p>
            {!statusFilter && loadTest.status === 'ready' && (
              <button
                onClick={handleStartTest}
                disabled={starting}
                className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white rounded-xl transition-all shadow-sm hover:shadow-md font-medium"
              >
                <Play className="w-5 h-5" />
                Start First Test Run
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden overflow-x-auto">
              <table className="w-full min-w-[600px]">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-100">
                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-700">Status</th>
                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-700">Started</th>
                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-700">Duration</th>
                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-700">Requests</th>
                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-700">Peak VUs</th>
                    <th className="text-left px-6 py-4 text-sm font-semibold text-gray-700">p95 Latency</th>
                    <th className="text-right px-6 py-4 text-sm font-semibold text-gray-700">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {testRuns.map((run) => (
                    <tr
                      key={run.id}
                      className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          {getStatusIcon(run.status)}
                          <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${getStatusBadge(run.status)}`}>
                            {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {formatDate(run.started_at)}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900 font-medium">
                        {formatDuration(run.duration_seconds)}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">
                        {run.total_requests?.toLocaleString() || '-'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">
                        {run.peak_vus || '-'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900">
                        {run.summary_metrics?.http_req_duration_p95
                          ? `${run.summary_metrics.http_req_duration_p95.toFixed(0)}ms`
                          : '-'}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Link
                          href={`/load-testing/${id}/runs/${run.id}`}
                          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary-600 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors"
                        >
                          <BarChart3 className="w-4 h-4" />
                          View Results
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-6 flex items-center justify-between">
                <div className="text-sm text-gray-600">
                  Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of {total} runs
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="inline-flex items-center gap-1 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-4 h-4" />
                    Previous
                  </button>
                  <span className="px-3 py-2 text-sm text-gray-600">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="inline-flex items-center gap-1 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
