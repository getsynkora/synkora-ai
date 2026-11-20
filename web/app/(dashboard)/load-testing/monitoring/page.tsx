'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  ArrowLeft,
  Plus,
  Activity,
  Trash2,
  CheckCircle,
  XCircle,
  AlertCircle,
  RefreshCw,
  ExternalLink,
  TestTube,
  Settings,
  Webhook,
  BarChart,
  Cloud,
} from 'lucide-react'
import {
  getMonitoringIntegrations,
  deleteMonitoringIntegration,
  testMonitoringConnection,
  type MonitoringIntegration,
} from '@/lib/api/load-testing'

export default function MonitoringIntegrationsPage() {
  const [integrations, setIntegrations] = useState<MonitoringIntegration[]>([])
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [deleteModal, setDeleteModal] = useState<{ show: boolean; integration: MonitoringIntegration | null }>({
    show: false,
    integration: null,
  })

  useEffect(() => {
    fetchIntegrations()
  }, [])

  const fetchIntegrations = async () => {
    try {
      setLoading(true)
      const response = await getMonitoringIntegrations()
      setIntegrations(response.items || [])
    } catch (err) {
      toast.error('Failed to load monitoring integrations')
    } finally {
      setLoading(false)
    }
  }

  const handleTest = async (integrationId: string) => {
    setTesting(integrationId)
    try {
      const result = await testMonitoringConnection(integrationId)
      if (result.success) {
        toast.success('Connection successful!')
      } else {
        toast.error(result.message || 'Connection failed')
      }
    } catch (err) {
      toast.error('Failed to test connection')
    } finally {
      setTesting(null)
    }
  }

  const handleDelete = async () => {
    if (!deleteModal.integration) return

    setDeleting(deleteModal.integration.id)
    try {
      await deleteMonitoringIntegration(deleteModal.integration.id)
      toast.success('Integration deleted')
      setDeleteModal({ show: false, integration: null })
      fetchIntegrations()
    } catch (err) {
      toast.error('Failed to delete integration')
    } finally {
      setDeleting(null)
    }
  }

  const getProviderIcon = (provider: string) => {
    switch (provider) {
      case 'datadog':
        return <BarChart className="w-5 h-5" />
      case 'otlp':
        return <Activity className="w-5 h-5" />
      case 'grafana_cloud':
        return <Cloud className="w-5 h-5" />
      case 'webhook':
        return <Webhook className="w-5 h-5" />
      default:
        return <Activity className="w-5 h-5" />
    }
  }

  const getProviderColor = (provider: string) => {
    const colors: Record<string, string> = {
      datadog: 'bg-sand-deep text-ink-soft',
      otlp: 'bg-sky-wash text-azure',
      grafana_cloud: 'bg-sand-deep text-warn',
      webhook: 'bg-leaf-wash text-leaf',
    }
    return colors[provider] || 'bg-sand text-ink-soft'
  }

  const getProviderLabel = (provider: string) => {
    const labels: Record<string, string> = {
      datadog: 'DataDog',
      otlp: 'OpenTelemetry',
      grafana_cloud: 'Grafana Cloud',
      webhook: 'Webhook',
    }
    return labels[provider] || provider
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleString()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-cream50/30">
        <div className="text-center">
          <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-ink-soft">Loading monitoring integrations…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-cream50/30 p-4 md:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/load-testing"
            className="inline-flex items-center gap-2 text-ink-soft hover:text-ink mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Load Testing
          </Link>

          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Monitoring Integrations</h1>
              <p className="text-ink-soft mt-1">
                Export test results to your favorite monitoring platforms
              </p>
            </div>

            <Link
              href="/load-testing/monitoring/create"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-ink hover:bg-ink/85 text-white rounded-xl transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm hover:shadow-md font-medium"
            >
              <Plus className="w-5 h-5" />
              Add Integration
            </Link>
          </div>
        </div>

        {/* Provider Cards */}
        <div className="mb-8 grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            { provider: 'datadog', name: 'DataDog', desc: 'APM & Metrics' },
            { provider: 'otlp', name: 'OpenTelemetry', desc: 'OTLP Export' },
            { provider: 'grafana_cloud', name: 'Grafana Cloud', desc: 'Prometheus' },
            { provider: 'webhook', name: 'Webhook', desc: 'Custom HTTP' },
          ].map((item) => (
            <div
              key={item.provider}
              className="bg-white rounded-xl shadow-sm border border-sand p-4 flex items-center gap-3"
            >
              <div className={`p-2.5 rounded-xl ${getProviderColor(item.provider)}`}>
                {getProviderIcon(item.provider)}
              </div>
              <div>
                <h3 className="font-medium text-ink">{item.name}</h3>
                <p className="text-xs text-ink-mute">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Integrations List */}
        {integrations.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-sm border border-sand p-12 text-center">
            <div className="w-32 h-32 mx-auto mb-6 relative">
              <div className="absolute inset-0 bg-ink hover:bg-ink/85 rounded-2xl transform rotate-6"></div>
              <div className="absolute inset-0 bg-white rounded-2xl shadow-sm border border-sand flex items-center justify-center">
                <Activity className="w-12 h-12 text-primary-500" />
              </div>
            </div>

            <h3 className="text-xl font-semibold text-ink mb-2">
              No monitoring integrations configured
            </h3>
            <p className="text-ink-soft mb-6 max-w-md mx-auto">
              Connect your monitoring platform to automatically export test results and metrics.
            </p>
            <Link
              href="/load-testing/monitoring/create"
              className="inline-flex items-center gap-2 px-6 py-3 bg-ink hover:bg-ink/85 text-white rounded-xl transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm hover:shadow-md font-medium"
            >
              <Plus className="w-5 h-5" />
              Add Integration
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {integrations.map((integration) => (
              <div
                key={integration.id}
                className="bg-white rounded-xl shadow-sm border border-sand hover:shadow-md transition-[color,background-color,border-color,box-shadow,opacity,transform]"
              >
                <div className="p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-4">
                      <div className={`p-3 rounded-xl ${getProviderColor(integration.provider)}`}>
                        {getProviderIcon(integration.provider)}
                      </div>
                      <div>
                        <div className="flex items-center gap-3">
                          <h3 className="font-semibold text-ink">{integration.name}</h3>
                          <span className="px-2 py-0.5 text-xs rounded-full bg-sand text-ink-soft">
                            {getProviderLabel(integration.provider)}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-sm">
                          {integration.is_active ? (
                            <span className="flex items-center gap-1 text-leaf">
                              <CheckCircle className="w-4 h-4" />
                              Active
                            </span>
                          ) : (
                            <span className="flex items-center gap-1 text-ink-mute">
                              <XCircle className="w-4 h-4" />
                              Inactive
                            </span>
                          )}
                          {integration.sync_status && (
                            <span className={`flex items-center gap-1 ${
                              integration.sync_status === 'success' ? 'text-leaf' :
                              integration.sync_status === 'failed' ? 'text-danger' :
                              'text-ink-mute'
                            }`}>
                              {integration.sync_status === 'success' ? (
                                <CheckCircle className="w-4 h-4" />
                              ) : integration.sync_status === 'failed' ? (
                                <AlertCircle className="w-4 h-4" />
                              ) : (
                                <RefreshCw className="w-4 h-4" />
                              )}
                              Last sync: {integration.sync_status}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleTest(integration.id)}
                        disabled={testing === integration.id}
                        className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary-600 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors disabled:opacity-50"
                      >
                        {testing === integration.id ? (
                          <RefreshCw className="w-4 h-4 motion-safe:animate-spin" />
                        ) : (
                          <TestTube className="w-4 h-4" />
                        )}
                        Test
                      </button>
                      <button
                        onClick={() => setDeleteModal({ show: true, integration })}
                        className="inline-flex items-center gap-1 px-3 py-2 text-sm text-danger hover:bg-blush-wash rounded-lg transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Integration Details */}
                  <div className="mt-4 pt-4 border-t border-sand grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-ink-mute">Last Sync</span>
                      <p className="text-ink font-medium">{formatDate(integration.last_sync_at)}</p>
                    </div>
                    <div>
                      <span className="text-ink-mute">Created</span>
                      <p className="text-ink font-medium">{formatDate(integration.created_at)}</p>
                    </div>
                    <div>
                      <span className="text-ink-mute">Export Settings</span>
                      <p className="text-ink font-medium">
                        {integration.export_settings?.auto_export ? 'Auto-export enabled' : 'Manual export'}
                      </p>
                    </div>
                  </div>

                  {/* Sync Error */}
                  {integration.sync_error && (
                    <div className="mt-4 p-3 bg-blush-wash border border-blush rounded-lg">
                      <div className="flex items-start gap-2">
                        <AlertCircle className="w-4 h-4 text-danger mt-0.5" />
                        <div>
                          <span className="text-sm font-medium text-wine">Sync Error</span>
                          <p className="text-sm text-danger mt-0.5">{integration.sync_error}</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete Modal */}
      {deleteModal.show && deleteModal.integration && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 bg-sand-deep rounded-xl">
                <Trash2 className="w-6 h-6 text-danger" />
              </div>
              <h3 className="text-lg font-semibold text-ink">Delete Integration</h3>
            </div>

            <p className="text-ink-soft mb-6">
              Are you sure you want to delete <span className="font-semibold text-ink">"{deleteModal.integration.name}"</span>?
              Test results will no longer be exported to this platform.
            </p>

            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteModal({ show: false, integration: null })}
                disabled={deleting !== null}
                className="px-4 py-2.5 text-sm font-medium text-ink-soft bg-sand rounded-lg hover:bg-line transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting !== null}
                className="px-4 py-2.5 text-sm font-medium text-white bg-danger rounded-lg hover:bg-danger transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {deleting === deleteModal.integration.id ? (
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
