'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  ArrowLeft,
  Activity,
  Save,
  BarChart,
  Cloud,
  Webhook,
  CheckCircle,
  AlertCircle,
} from 'lucide-react'
import {
  createMonitoringIntegration,
  getMonitoringProviderSchemas,
} from '@/lib/api/load-testing'

type ProviderType = 'datadog' | 'otlp' | 'grafana_cloud' | 'webhook'

interface ProviderConfig {
  icon: React.ReactNode
  name: string
  description: string
  color: string
}

const PROVIDERS: Record<ProviderType, ProviderConfig> = {
  datadog: {
    icon: <BarChart className="w-6 h-6" />,
    name: 'DataDog',
    description: 'Export metrics to DataDog APM',
    color: 'bg-purple-100 text-purple-600 border-purple-200',
  },
  otlp: {
    icon: <Activity className="w-6 h-6" />,
    name: 'OpenTelemetry',
    description: 'Export via OTLP protocol',
    color: 'bg-blue-100 text-blue-600 border-blue-200',
  },
  grafana_cloud: {
    icon: <Cloud className="w-6 h-6" />,
    name: 'Grafana Cloud',
    description: 'Push to Prometheus remote write',
    color: 'bg-orange-100 text-orange-600 border-orange-200',
  },
  webhook: {
    icon: <Webhook className="w-6 h-6" />,
    name: 'Webhook',
    description: 'Send to custom HTTP endpoint',
    color: 'bg-green-100 text-green-600 border-green-200',
  },
}

export default function CreateMonitoringIntegrationPage() {
  const router = useRouter()
  const [saving, setSaving] = useState(false)
  const [schemas, setSchemas] = useState<Record<string, any>>({})

  // Form state
  const [name, setName] = useState('')
  const [provider, setProvider] = useState<ProviderType>('datadog')
  const [autoExport, setAutoExport] = useState(true)

  // Provider-specific config
  const [datadogConfig, setDatadogConfig] = useState({
    api_key: '',
    app_key: '',
    site: 'datadoghq.com',
    metric_prefix: 'loadtest.',
    tags: '',
  })

  const [otlpConfig, setOtlpConfig] = useState({
    endpoint: '',
    headers: '',
    protocol: 'grpc',
  })

  const [grafanaConfig, setGrafanaConfig] = useState({
    prometheus_url: '',
    username: '',
    api_key: '',
  })

  const [webhookConfig, setWebhookConfig] = useState({
    url: '',
    method: 'POST',
    headers: '',
    batch_size: 100,
  })

  useEffect(() => {
    fetchSchemas()
  }, [])

  const fetchSchemas = async () => {
    try {
      const data = await getMonitoringProviderSchemas()
      setSchemas(data)
    } catch (err) {
      console.error('Failed to fetch schemas:', err)
    }
  }

  const getConfigForProvider = (): Record<string, any> => {
    switch (provider) {
      case 'datadog':
        return {
          api_key: datadogConfig.api_key,
          app_key: datadogConfig.app_key,
          site: datadogConfig.site,
          metric_prefix: datadogConfig.metric_prefix,
          tags: datadogConfig.tags.split(',').map(t => t.trim()).filter(Boolean),
        }
      case 'otlp':
        return {
          endpoint: otlpConfig.endpoint,
          headers: otlpConfig.headers
            ? Object.fromEntries(
                otlpConfig.headers.split(',').map(h => h.trim().split(':').map(s => s.trim()))
              )
            : {},
          protocol: otlpConfig.protocol,
        }
      case 'grafana_cloud':
        return {
          prometheus_url: grafanaConfig.prometheus_url,
          username: grafanaConfig.username,
          api_key: grafanaConfig.api_key,
        }
      case 'webhook':
        return {
          url: webhookConfig.url,
          method: webhookConfig.method,
          headers: webhookConfig.headers
            ? Object.fromEntries(
                webhookConfig.headers.split(',').map(h => h.trim().split(':').map(s => s.trim()))
              )
            : {},
          batch_size: webhookConfig.batch_size,
        }
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!name.trim()) {
      toast.error('Please enter a name')
      return
    }

    const config = getConfigForProvider()

    // Validate required fields
    if (provider === 'datadog' && (!datadogConfig.api_key || !datadogConfig.app_key)) {
      toast.error('DataDog API key and App key are required')
      return
    }
    if (provider === 'otlp' && !otlpConfig.endpoint) {
      toast.error('OTLP endpoint is required')
      return
    }
    if (provider === 'grafana_cloud' && (!grafanaConfig.prometheus_url || !grafanaConfig.api_key)) {
      toast.error('Grafana Prometheus URL and API key are required')
      return
    }
    if (provider === 'webhook' && !webhookConfig.url) {
      toast.error('Webhook URL is required')
      return
    }

    setSaving(true)
    try {
      await createMonitoringIntegration({
        name: name.trim(),
        provider,
        config,
        export_settings: {
          auto_export: autoExport,
        },
      })

      toast.success('Monitoring integration created!')
      router.push('/load-testing/monitoring')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create integration')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-primary-50/30 p-4 md:p-6">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/load-testing/monitoring"
            className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Monitoring
          </Link>
          <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Add Monitoring Integration</h1>
          <p className="text-gray-600 mt-1">
            Connect your monitoring platform to export test results
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Basic Info */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Basic Information</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Integration Name *
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Production DataDog"
                  className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Provider
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {(Object.entries(PROVIDERS) as [ProviderType, ProviderConfig][]).map(([key, config]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setProvider(key)}
                      className={`p-4 rounded-xl border-2 transition-all text-left ${
                        provider === key
                          ? `${config.color} border-current`
                          : 'bg-white border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={provider === key ? '' : 'text-gray-400'}>
                          {config.icon}
                        </div>
                        <div>
                          <div className={`font-medium ${provider === key ? '' : 'text-gray-900'}`}>
                            {config.name}
                          </div>
                          <div className={`text-xs ${provider === key ? 'opacity-80' : 'text-gray-500'}`}>
                            {config.description}
                          </div>
                        </div>
                        {provider === key && (
                          <CheckCircle className="w-5 h-5 ml-auto" />
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Provider-specific Config */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              {PROVIDERS[provider].icon}
              {PROVIDERS[provider].name} Configuration
            </h2>

            {provider === 'datadog' && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      API Key *
                    </label>
                    <input
                      type="password"
                      value={datadogConfig.api_key}
                      onChange={(e) => setDatadogConfig({ ...datadogConfig, api_key: e.target.value })}
                      placeholder="Your DataDog API key"
                      className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      App Key *
                    </label>
                    <input
                      type="password"
                      value={datadogConfig.app_key}
                      onChange={(e) => setDatadogConfig({ ...datadogConfig, app_key: e.target.value })}
                      placeholder="Your DataDog App key"
                      className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Site
                    </label>
                    <select
                      value={datadogConfig.site}
                      onChange={(e) => setDatadogConfig({ ...datadogConfig, site: e.target.value })}
                      className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    >
                      <option value="datadoghq.com">US1 (datadoghq.com)</option>
                      <option value="us3.datadoghq.com">US3 (us3.datadoghq.com)</option>
                      <option value="us5.datadoghq.com">US5 (us5.datadoghq.com)</option>
                      <option value="datadoghq.eu">EU (datadoghq.eu)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Metric Prefix
                    </label>
                    <input
                      type="text"
                      value={datadogConfig.metric_prefix}
                      onChange={(e) => setDatadogConfig({ ...datadogConfig, metric_prefix: e.target.value })}
                      placeholder="loadtest."
                      className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Tags (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={datadogConfig.tags}
                    onChange={(e) => setDatadogConfig({ ...datadogConfig, tags: e.target.value })}
                    placeholder="env:production, team:platform"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
              </div>
            )}

            {provider === 'otlp' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    OTLP Endpoint *
                  </label>
                  <input
                    type="url"
                    value={otlpConfig.endpoint}
                    onChange={(e) => setOtlpConfig({ ...otlpConfig, endpoint: e.target.value })}
                    placeholder="https://otel-collector:4317"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Protocol
                  </label>
                  <select
                    value={otlpConfig.protocol}
                    onChange={(e) => setOtlpConfig({ ...otlpConfig, protocol: e.target.value })}
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  >
                    <option value="grpc">gRPC</option>
                    <option value="http">HTTP/Protobuf</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Headers (comma-separated key:value)
                  </label>
                  <input
                    type="text"
                    value={otlpConfig.headers}
                    onChange={(e) => setOtlpConfig({ ...otlpConfig, headers: e.target.value })}
                    placeholder="Authorization:Bearer token, X-Custom:value"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
              </div>
            )}

            {provider === 'grafana_cloud' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Prometheus Remote Write URL *
                  </label>
                  <input
                    type="url"
                    value={grafanaConfig.prometheus_url}
                    onChange={(e) => setGrafanaConfig({ ...grafanaConfig, prometheus_url: e.target.value })}
                    placeholder="https://prometheus-us-central1.grafana.net/api/prom/push"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Username
                    </label>
                    <input
                      type="text"
                      value={grafanaConfig.username}
                      onChange={(e) => setGrafanaConfig({ ...grafanaConfig, username: e.target.value })}
                      placeholder="Instance ID or username"
                      className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      API Key *
                    </label>
                    <input
                      type="password"
                      value={grafanaConfig.api_key}
                      onChange={(e) => setGrafanaConfig({ ...grafanaConfig, api_key: e.target.value })}
                      placeholder="Grafana Cloud API key"
                      className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>
                </div>
              </div>
            )}

            {provider === 'webhook' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Webhook URL *
                  </label>
                  <input
                    type="url"
                    value={webhookConfig.url}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, url: e.target.value })}
                    placeholder="https://your-server.com/webhook"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      HTTP Method
                    </label>
                    <select
                      value={webhookConfig.method}
                      onChange={(e) => setWebhookConfig({ ...webhookConfig, method: e.target.value })}
                      className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    >
                      <option value="POST">POST</option>
                      <option value="PUT">PUT</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Batch Size
                    </label>
                    <input
                      type="number"
                      value={webhookConfig.batch_size}
                      onChange={(e) => setWebhookConfig({ ...webhookConfig, batch_size: parseInt(e.target.value) })}
                      min="1"
                      max="1000"
                      className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Headers (comma-separated key:value)
                  </label>
                  <input
                    type="text"
                    value={webhookConfig.headers}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, headers: e.target.value })}
                    placeholder="Authorization:Bearer token, Content-Type:application/json"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Export Settings */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Export Settings</h2>

            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={autoExport}
                onChange={(e) => setAutoExport(e.target.checked)}
                className="w-5 h-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <div>
                <span className="font-medium text-gray-900">Auto-export after test completion</span>
                <p className="text-sm text-gray-500">
                  Automatically export results when a test run completes
                </p>
              </div>
            </label>
          </div>

          {/* Submit */}
          <div className="flex justify-end gap-4">
            <Link
              href="/load-testing/monitoring"
              className="px-6 py-2.5 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors font-medium"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Create Integration
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
