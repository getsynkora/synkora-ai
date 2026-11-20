'use client'

import { useState, useEffect, useRef, use } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import {
  ArrowLeft,
  Activity,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  StopCircle,
  Download,
  RefreshCw,
  Zap,
  Timer,
  Server,
  TrendingUp,
  BarChart3,
  Code,
} from 'lucide-react'
import {
  getTestRun,
  getTestResults,
  cancelTestRun,
  exportTestResults,
  type TestRun,
  type TestResultsResponse,
} from '@/lib/api/load-testing'

interface MetricCard {
  label: string
  value: string | number
  unit?: string
  icon: React.ReactNode
  trend?: 'up' | 'down' | 'neutral'
  color: string
}

export default function TestRunDashboardPage({ params }: { params: Promise<{ id: string; runId: string }> }) {
  const { id, runId } = use(params)
  const router = useRouter()
  const [testRun, setTestRun] = useState<TestRun | null>(null)
  const [results, setResults] = useState<TestResultsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [cancelling, setCancelling] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [showScript, setShowScript] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    fetchData()
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
      }
    }
  }, [runId])

  useEffect(() => {
    // Auto-refresh while test is running
    if (autoRefresh && testRun && ['pending', 'initializing', 'running'].includes(testRun.status)) {
      refreshIntervalRef.current = setInterval(fetchData, 3000)
    } else if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current)
    }
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
      }
    }
  }, [autoRefresh, testRun?.status])

  const fetchData = async () => {
    try {
      const [runData, resultsData] = await Promise.all([
        getTestRun(runId),
        getTestResults(runId).catch(() => null),
      ])
      setTestRun(runData)
      setResults(resultsData)
    } catch (err) {
      if (loading) {
        toast.error('Failed to load test run')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!testRun) return

    setCancelling(true)
    try {
      await cancelTestRun(runId)
      toast.success('Test run cancelled')
      fetchData()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to cancel test')
    } finally {
      setCancelling(false)
    }
  }

  const handleExport = async (format: 'json' | 'csv' | 'pdf') => {
    setExporting(true)
    try {
      const result = await exportTestResults(runId, { format, include_time_series: true })
      window.open(result.download_url, '_blank')
      toast.success(`Export ready (${format.toUpperCase()})`)
    } catch (err) {
      toast.error('Failed to export results')
    } finally {
      setExporting(false)
    }
  }

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      pending: 'bg-sky-wash text-azure',
      initializing: 'bg-sand-deep text-gold',
      running: 'bg-leaf-wash text-forest',
      stopping: 'bg-sand-deep text-gold',
      completed: 'bg-leaf-wash text-forest',
      failed: 'bg-blush-wash text-danger',
      cancelled: 'bg-sand text-ink-soft',
    }
    return styles[status] || styles.pending
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-6 h-6 text-leaf" />
      case 'failed':
        return <XCircle className="w-6 h-6 text-danger" />
      case 'cancelled':
        return <XCircle className="w-6 h-6 text-ink-soft" />
      case 'running':
      case 'initializing':
        return <Activity className="w-6 h-6 text-leaf motion-safe:animate-pulse" />
      default:
        return <Clock className="w-6 h-6 text-azure" />
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleString()
  }

  const formatDuration = (seconds: number | null | undefined) => {
    if (seconds === null || seconds === undefined) return '-'
    if (seconds < 60) return `${seconds.toFixed(1)}s`
    const mins = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return `${mins}m ${secs}s`
  }

  const formatNumber = (num: number | null | undefined, decimals = 0) => {
    if (num === null || num === undefined) return '-'
    return num.toLocaleString(undefined, { maximumFractionDigits: decimals })
  }

  const getMetricCards = (): MetricCard[] => {
    const summary = results?.summary || testRun?.summary_metrics || {}

    return [
      {
        label: 'Total Requests',
        value: formatNumber(testRun?.total_requests || summary.http_reqs),
        icon: <Server className="w-5 h-5" />,
        color: 'text-primary-600 bg-primary-100',
      },
      {
        label: 'Requests/sec',
        value: formatNumber(summary.http_reqs_per_sec, 1),
        icon: <Zap className="w-5 h-5" />,
        color: 'text-leaf bg-leaf-wash',
      },
      {
        label: 'Peak VUs',
        value: formatNumber(testRun?.peak_vus || summary.vus_max),
        icon: <TrendingUp className="w-5 h-5" />,
        color: 'text-azure bg-sky-wash',
      },
      {
        label: 'Duration',
        value: formatDuration(testRun?.duration_seconds),
        icon: <Timer className="w-5 h-5" />,
        color: 'text-plum bg-blush-wash',
      },
      {
        label: 'p50 Latency',
        value: summary.http_req_duration_p50 ? `${formatNumber(summary.http_req_duration_p50, 0)}ms` : '-',
        icon: <Activity className="w-5 h-5" />,
        color: 'text-azure bg-sky-wash',
      },
      {
        label: 'p95 Latency',
        value: summary.http_req_duration_p95 ? `${formatNumber(summary.http_req_duration_p95, 0)}ms` : '-',
        icon: <Activity className="w-5 h-5" />,
        color: 'text-warn bg-sand-deep',
      },
      {
        label: 'p99 Latency',
        value: summary.http_req_duration_p99 ? `${formatNumber(summary.http_req_duration_p99, 0)}ms` : '-',
        icon: <Activity className="w-5 h-5" />,
        color: 'text-leaf bg-blush-wash',
      },
      {
        label: 'Error Rate',
        value: summary.http_req_failed !== undefined ? `${(summary.http_req_failed * 100).toFixed(2)}%` : '-',
        icon: <AlertCircle className="w-5 h-5" />,
        color: summary.http_req_failed && summary.http_req_failed > 0.01 ? 'text-danger bg-blush-wash' : 'text-leaf bg-leaf-wash',
      },
    ]
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-cream50/30">
        <div className="text-center">
          <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-ink-soft">Loading test results…</p>
        </div>
      </div>
    )
  }

  if (!testRun) {
    return (
      <div className="min-h-screen bg-cream50/30 p-4 md:p-6">
        <div className="max-w-4xl mx-auto text-center py-12">
          <AlertCircle className="w-16 h-16 text-taupe mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-ink mb-2">Test Run Not Found</h2>
          <Link href={`/load-testing/${id}/runs`} className="text-primary-600 hover:text-primary-700">
            Back to Test Runs
          </Link>
        </div>
      </div>
    )
  }

  const isActive = ['pending', 'initializing', 'running', 'stopping'].includes(testRun.status)

  return (
    <div className="min-h-screen bg-cream50/30 p-4 md:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link
            href={`/load-testing/${id}/runs`}
            className="inline-flex items-center gap-2 text-ink-soft hover:text-ink mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Test Runs
          </Link>

          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                {getStatusIcon(testRun.status)}
                <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Test Run Results</h1>
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusBadge(testRun.status)}`}>
                  {testRun.status.charAt(0).toUpperCase() + testRun.status.slice(1)}
                </span>
              </div>
              <p className="text-ink-soft">
                Started: {formatDate(testRun.started_at)}
                {testRun.completed_at && ` • Completed: ${formatDate(testRun.completed_at)}`}
              </p>
            </div>

            <div className="flex gap-3">
              {isActive && (
                <>
                  <label className="inline-flex items-center gap-2 px-4 py-2.5 bg-white border border-line rounded-xl cursor-pointer hover:bg-cream">
                    <input
                      type="checkbox"
                      checked={autoRefresh}
                      onChange={(e) => setAutoRefresh(e.target.checked)}
                      className="rounded border-taupe text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-sm text-ink-soft">Auto-refresh</span>
                  </label>
                  <button
                    onClick={handleCancel}
                    disabled={cancelling || testRun.status === 'stopping'}
                    className="inline-flex items-center gap-2 px-4 py-2.5 border border-blush bg-blush-wash text-danger rounded-xl hover:bg-blush-wash transition-colors font-medium disabled:opacity-50"
                  >
                    {cancelling ? (
                      <div className="w-4 h-4 border-2 border-danger border-t-transparent rounded-full motion-safe:animate-spin" />
                    ) : (
                      <StopCircle className="w-4 h-4" />
                    )}
                    Cancel Test
                  </button>
                </>
              )}
              {!isActive && (
                <div className="flex gap-2">
                  <button
                    onClick={() => handleExport('json')}
                    disabled={exporting}
                    className="inline-flex items-center gap-2 px-4 py-2.5 border border-line bg-white text-ink-soft rounded-xl hover:bg-cream transition-colors font-medium disabled:opacity-50"
                  >
                    <Download className="w-4 h-4" />
                    JSON
                  </button>
                  <button
                    onClick={() => handleExport('csv')}
                    disabled={exporting}
                    className="inline-flex items-center gap-2 px-4 py-2.5 border border-line bg-white text-ink-soft rounded-xl hover:bg-cream transition-colors font-medium disabled:opacity-50"
                  >
                    <Download className="w-4 h-4" />
                    CSV
                  </button>
                </div>
              )}
              <button
                onClick={fetchData}
                disabled={loading}
                className="inline-flex items-center gap-2 px-4 py-2.5 border border-line bg-white text-ink-soft rounded-xl hover:bg-cream transition-colors font-medium"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'motion-safe:animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {testRun.error_message && (
          <div className="mb-6 bg-blush-wash border border-blush rounded-xl p-4">
            <div className="flex items-start gap-3">
              <XCircle className="w-5 h-5 text-danger mt-0.5" />
              <div>
                <h3 className="font-medium text-wine">Test Run Failed</h3>
                <p className="text-danger mt-1">{testRun.error_message}</p>
              </div>
            </div>
          </div>
        )}

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {getMetricCards().map((metric, index) => (
            <div
              key={index}
              className="bg-white rounded-xl shadow-sm border border-sand p-5"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className={`p-2.5 rounded-xl ${metric.color}`}>
                  {metric.icon}
                </div>
              </div>
              <div className="text-sm text-ink-soft mb-1">{metric.label}</div>
              <div className="text-2xl font-bold text-ink">{metric.value}</div>
            </div>
          ))}
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Latency Distribution */}
          <div className="bg-white rounded-xl shadow-sm border border-sand p-6">
            <h2 className="text-lg font-semibold text-ink mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary-600" />
              Latency Distribution
            </h2>
            <div className="h-64 flex items-center justify-center">
              {results?.summary ? (
                <div className="w-full space-y-4">
                  {[
                    { label: 'p50', value: results.summary.http_req_duration_p50, color: 'bg-azure' },
                    { label: 'p95', value: results.summary.http_req_duration_p95, color: 'bg-warn' },
                    { label: 'p99', value: results.summary.http_req_duration_p99, color: 'bg-ink' },
                  ].map((item) => {
                    const maxValue = Math.max(
                      results.summary.http_req_duration_p50 || 0,
                      results.summary.http_req_duration_p95 || 0,
                      results.summary.http_req_duration_p99 || 0
                    )
                    const width = maxValue > 0 && item.value ? (item.value / maxValue) * 100 : 0
                    return (
                      <div key={item.label} className="space-y-1">
                        <div className="flex justify-between text-sm">
                          <span className="text-ink-soft">{item.label}</span>
                          <span className="font-medium text-ink">
                            {item.value ? `${item.value.toFixed(0)}ms` : '-'}
                          </span>
                        </div>
                        <div className="h-4 bg-sand rounded-full overflow-hidden">
                          <div
                            className={`h-full ${item.color} rounded-full transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-500`}
                            style={{ width: `${width}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <p className="text-ink-mute">No latency data available</p>
              )}
            </div>
          </div>

          {/* AI Metrics */}
          <div className="bg-white rounded-xl shadow-sm border border-sand p-6">
            <h2 className="text-lg font-semibold text-ink mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary-600" />
              AI-Specific Metrics
            </h2>
            <div className="h-64 flex items-center justify-center">
              {results?.summary?.ttft_p50 || results?.summary?.tokens_per_sec_avg ? (
                <div className="w-full space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 bg-primary-50 rounded-xl">
                      <div className="text-sm text-primary-600 mb-1">TTFT p50</div>
                      <div className="text-2xl font-bold text-primary-900">
                        {results.summary.ttft_p50 ? `${results.summary.ttft_p50.toFixed(0)}ms` : '-'}
                      </div>
                      <div className="text-xs text-primary-600 mt-1">Time to First Token</div>
                    </div>
                    <div className="p-4 bg-leaf-wash rounded-xl">
                      <div className="text-sm text-leaf mb-1">TTFT p95</div>
                      <div className="text-2xl font-bold text-forest">
                        {results.summary.ttft_p95 ? `${results.summary.ttft_p95.toFixed(0)}ms` : '-'}
                      </div>
                      <div className="text-xs text-leaf mt-1">95th percentile</div>
                    </div>
                  </div>
                  <div className="p-4 bg-sand-deep rounded-xl">
                    <div className="text-sm text-plum mb-1">Tokens/sec (avg)</div>
                    <div className="text-2xl font-bold text-wine">
                      {results.summary.tokens_per_sec_avg
                        ? results.summary.tokens_per_sec_avg.toFixed(1)
                        : '-'}
                    </div>
                    <div className="text-xs text-plum mt-1">Average generation speed</div>
                  </div>
                </div>
              ) : (
                <p className="text-ink-mute">No AI metrics available</p>
              )}
            </div>
          </div>
        </div>

        {/* K6 Script */}
        {testRun.k6_script && (
          <div className="bg-white rounded-xl shadow-sm border border-sand p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-ink flex items-center gap-2">
                <Code className="w-5 h-5 text-primary-600" />
                Generated K6 Script
              </h2>
              <button
                onClick={() => setShowScript(!showScript)}
                className="text-sm text-primary-600 hover:text-primary-700"
              >
                {showScript ? 'Hide Script' : 'Show Script'}
              </button>
            </div>
            {showScript && (
              <pre className="bg-ink text-sand p-4 rounded-lg overflow-x-auto text-sm max-h-96">
                <code>{testRun.k6_script}</code>
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
