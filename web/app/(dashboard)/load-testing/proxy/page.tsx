'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  CheckCircle,
  Copy,
  Eye,
  EyeOff,
  Key,
  RefreshCw,
  Server,
  Settings,
  Trash2,
  XCircle,
} from 'lucide-react'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'
import {
  deleteProxyConfig,
  getProxyConfigs,
  regenerateProxyApiKey,
  type ProxyConfig,
} from '@/lib/api/load-testing'

const providerMetadata: Record<
  string,
  {
    label: string
    badgeClassName: string
    endpoint: string
  }
> = {
  openai: {
    label: 'OpenAI Compatible',
    badgeClassName: 'bg-leaf-wash text-leaf',
    endpoint: '/proxy/v1/chat/completions',
  },
  anthropic: {
    label: 'Anthropic',
    badgeClassName: 'bg-sand text-bark',
    endpoint: '/proxy/v1/messages',
  },
  google: {
    label: 'Google',
    badgeClassName: 'bg-sky-wash text-azure',
    endpoint: '/proxy/v1/models/gemini-pro:generateContent',
  },
}

const fallbackProvider = {
  label: 'Custom Provider',
  badgeClassName: 'bg-paper text-ink-soft',
  endpoint: '/proxy/v1',
}

export default function ProxyConfigsPage() {
  const [proxyConfigs, setProxyConfigs] = useState<ProxyConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [regenerating, setRegenerating] = useState<string | null>(null)
  const [deleteModal, setDeleteModal] = useState<{ show: boolean; config: ProxyConfig | null }>({
    show: false,
    config: null,
  })
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set())
  const [newApiKey, setNewApiKey] = useState<{ id: string; key: string } | null>(null)

  useEffect(() => {
    fetchProxyConfigs()
  }, [])

  const fetchProxyConfigs = async () => {
    try {
      setLoading(true)
      const response = await getProxyConfigs()
      setProxyConfigs(response.items || [])
    } catch {
      toast.error('Failed to load proxy configurations')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteModal.config) return

    setDeleting(deleteModal.config.id)
    try {
      await deleteProxyConfig(deleteModal.config.id)
      toast.success('Proxy configuration deleted')
      setDeleteModal({ show: false, config: null })
      fetchProxyConfigs()
    } catch {
      toast.error('Failed to delete proxy configuration')
    } finally {
      setDeleting(null)
    }
  }

  const handleRegenerateKey = async (configId: string) => {
    setRegenerating(configId)
    try {
      const result = await regenerateProxyApiKey(configId)
      setNewApiKey({ id: configId, key: result.api_key })
      setVisibleKeys((prev) => new Set(prev).add(configId))
      toast.success('API key regenerated')
    } catch {
      toast.error('Failed to regenerate API key')
    } finally {
      setRegenerating(null)
    }
  }

  const toggleKeyVisibility = (configId: string) => {
    setVisibleKeys((prev) => {
      const next = new Set(prev)
      if (next.has(configId)) {
        next.delete(configId)
      } else {
        next.add(configId)
      }
      return next
    })
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  }

  const formatDate = (dateString: string) =>
    new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })

  const getProviderMeta = (provider: string) =>
    providerMetadata[provider] || {
      ...fallbackProvider,
      label: provider || fallbackProvider.label,
    }

  const getVisibleKey = (config: ProxyConfig) => {
    if (newApiKey?.id === config.id) return newApiKey.key
    if (visibleKeys.has(config.id)) return `${config.api_key_prefix}...`
    return '••••••••••••••••'
  }

  const getCopyableKey = (config: ProxyConfig) => {
    if (newApiKey?.id === config.id) return newApiKey.key
    return `${config.api_key_prefix}...`
  }

  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.synkora.com'
  const activeConfigs = proxyConfigs.filter((config) => config.is_active).length
  const totalRequests = proxyConfigs.reduce((sum, config) => sum + config.usage_count, 0)
  const totalTokens = proxyConfigs.reduce((sum, config) => sum + config.total_tokens_generated, 0)

  if (loading) {
    return (
      <div className="dashboard-resource-page flex min-h-screen items-center justify-center p-6">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 motion-safe:animate-spin rounded-full border-b-2 border-ink" />
          <p className="text-ink-soft">Loading proxy configurations…</p>
        </div>
      </div>
    )
  }

  return (
    <>
      <DashboardPageShell
        title="Proxy Configurations"
        description="Route AI agent load tests through mock provider endpoints so you can model latency, token output, and failures without burning production credits."
        icon={Server}
        badge="Load Testing Lab"
        backHref="/load-testing"
        backLabel="Back to Load Testing"
        maxWidthClassName="max-w-6xl"
        breadcrumbs={[
          { label: 'Home', href: '/' },
          { label: 'Load Testing', href: '/load-testing' },
          { label: 'Proxy Configurations' },
        ]}
        actions={
          <div className="flex flex-wrap gap-3">
            <Link
              href="/load-testing/proxy/create"
              className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
            >
              <Server className="h-4 w-4" />
              Create Proxy
            </Link>
          </div>
        }
        stats={[
          { label: 'Total configs', value: proxyConfigs.length },
          { label: 'Active', value: activeConfigs },
          { label: 'Requests served', value: totalRequests.toLocaleString() },
        ]}
      >
        <div className="mb-6 grid gap-4 lg:grid-cols-[1.35fr_0.95fr]">
          <DashboardPagePanel className="overflow-hidden p-6">
            <div className="flex items-start gap-4">
              <div className="rounded-[1.25rem] bg-sand p-3 shadow-soft">
                <Server className="h-6 w-6 text-ink" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-ink">Synkora proxy endpoints</h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-soft">
                  Swap your live provider URL for a mock Synkora endpoint during load testing. Each config
                  can model realistic latency, token volumes, and injected failures.
                </p>
                <div className="mt-5 space-y-3">
                  {Object.entries(providerMetadata).map(([provider, meta]) => (
                    <div
                      key={provider}
                      className="flex flex-col gap-2 rounded-[1.2rem] border border-sand-deep bg-cream p-4 md:flex-row md:items-center md:justify-between"
                    >
                      <div>
                        <p className="text-sm font-semibold text-ink">{meta.label}</p>
                        <p className="text-xs text-clay">
                          Mock endpoint
                        </p>
                      </div>
                      <code className="overflow-x-auto rounded-xl bg-white px-3 py-2 text-xs text-ink-soft shadow-inner">
                        {apiBaseUrl}
                        {meta.endpoint}
                      </code>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </DashboardPagePanel>

          <DashboardPagePanel className="p-6">
            <p className="text-[11px] font-semibold text-clay">
              System Snapshot
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
              <div className="rounded-[1.25rem] bg-sky-wash p-4">
                <p className="text-sm text-azure">Requests proxied</p>
                <p className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-azure">
                  {totalRequests.toLocaleString()}
                </p>
              </div>
              <div className="rounded-[1.25rem] bg-leaf-wash p-4">
                <p className="text-sm text-forest">Tokens generated</p>
                <p className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-forest">
                  {(totalTokens / 1000).toFixed(1)}K
                </p>
              </div>
              <div className="rounded-[1.25rem] bg-sand p-4">
                <p className="text-sm text-bark">Ready for</p>
                <p className="mt-2 text-base font-semibold text-ink">
                  Load-safe testing across OpenAI, Anthropic, and Google style endpoints
                </p>
              </div>
            </div>
          </DashboardPagePanel>
        </div>

        {proxyConfigs.length === 0 ? (
          <DashboardPagePanel className="p-12 text-center">
            <div className="relative mx-auto mb-6 h-32 w-32">
              <div className="absolute inset-0 rotate-6 rounded-2xl bg-sand" />
              <div className="absolute inset-0 flex items-center justify-center rounded-2xl border border-sand bg-white shadow-sm">
                <Server className="h-12 w-12 text-ink" />
              </div>
            </div>

            <h3 className="mb-2 text-xl font-semibold text-ink">Create your first proxy configuration</h3>
            <p className="mx-auto mb-6 max-w-md text-ink-soft">
              Build a branded load-testing setup that mirrors provider behavior without touching your paid API quota.
            </p>
            <Link
              href="/load-testing/proxy/create"
              className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-6 py-3 font-semibold text-white transition-colors hover:bg-black"
            >
              <Server className="h-5 w-5" />
              Create Proxy Config
            </Link>
          </DashboardPagePanel>
        ) : (
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {proxyConfigs.map((config) => {
              const providerMeta = getProviderMeta(config.provider)
              const showingNewKey = newApiKey?.id === config.id

              return (
                <DashboardPagePanel key={config.id} className="overflow-hidden">
                  <div className="border-b border-sand-deep bg-white px-6 py-5">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <div className="rounded-[1rem] bg-sand p-2.5">
                          <Server className="h-5 w-5 text-ink" />
                        </div>
                        <div>
                          <h3 className="text-lg font-semibold text-ink">{config.name}</h3>
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            <span
                              className={`rounded-full px-2.5 py-1 text-xs font-semibold ${providerMeta.badgeClassName}`}
                            >
                              {providerMeta.label}
                            </span>
                            <span
                              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${
                                config.is_active
                                  ? 'bg-leaf-wash text-forest'
                                  : 'bg-paper text-ink-mute'
                              }`}
                            >
                              {config.is_active ? (
                                <CheckCircle className="h-3.5 w-3.5" />
                              ) : (
                                <XCircle className="h-3.5 w-3.5" />
                              )}
                              {config.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => setDeleteModal({ show: true, config })}
                        className="inline-flex items-center gap-1 rounded-[0.9rem] px-3 py-2 text-sm font-medium text-wine transition-colors hover:bg-blush-wash"
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </button>
                    </div>
                  </div>

                  <div className="space-y-5 p-6">
                    <div className="rounded-[1.2rem] border border-sand-deep bg-cream p-4">
                      <div className="mb-3 flex items-center justify-between gap-4">
                        <span className="flex items-center gap-1 text-xs font-semibold text-clay">
                          <Key className="h-3.5 w-3.5" />
                          API Key
                        </span>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => toggleKeyVisibility(config.id)}
                            className="rounded-lg p-2 text-ash transition-colors hover:bg-white hover:text-ink-soft"
                            aria-label={visibleKeys.has(config.id) ? 'Hide API key' : 'Show API key'}
                          >
                            {visibleKeys.has(config.id) ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </button>
                          <button
                            onClick={() => copyToClipboard(getCopyableKey(config))}
                            className="rounded-lg p-2 text-ash transition-colors hover:bg-white hover:text-ink-soft"
                            aria-label="Copy API key"
                          >
                            <Copy className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleRegenerateKey(config.id)}
                            disabled={regenerating === config.id}
                            className="rounded-lg p-2 text-ash transition-colors hover:bg-white hover:text-ink-soft disabled:opacity-50"
                            aria-label="Regenerate API key"
                          >
                            <RefreshCw
                              className={`h-4 w-4 ${regenerating === config.id ? 'motion-safe:animate-spin' : ''}`}
                            />
                          </button>
                        </div>
                      </div>
                      <code className="block overflow-x-auto rounded-xl bg-white px-3 py-3 font-mono text-sm text-ink-soft shadow-inner">
                        {getVisibleKey(config)}
                      </code>
                      {showingNewKey ? (
                        <p className="mt-2 text-xs font-medium text-gold">
                          Save this regenerated key now. It will not be shown again.
                        </p>
                      ) : null}
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      <div className="rounded-[1.1rem] bg-sky-wash p-3 text-center">
                        <div className="text-lg font-semibold text-azure">
                          {config.usage_count.toLocaleString()}
                        </div>
                        <div className="text-xs text-azure">Requests</div>
                      </div>
                      <div className="rounded-[1.1rem] bg-leaf-wash p-3 text-center">
                        <div className="text-lg font-semibold text-forest">
                          {(config.total_tokens_generated / 1000).toFixed(1)}K
                        </div>
                        <div className="text-xs text-forest">Tokens</div>
                      </div>
                      <div className="rounded-[1.1rem] bg-sand p-3 text-center">
                        <div className="text-lg font-semibold text-bark">{config.rate_limit}</div>
                        <div className="text-xs text-bark">RPS Limit</div>
                      </div>
                    </div>

                    <div className="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
                      <div className="rounded-[1.2rem] border border-sand-deep bg-white/80 p-4">
                        <div className="mb-2 flex items-center gap-2">
                          <Settings className="h-4 w-4 text-bark" />
                          <span className="text-sm font-semibold text-ink">Mock behavior</span>
                        </div>
                        <div className="space-y-2 text-sm text-ink-soft">
                          <p>
                            Latency: {config.mock_config?.latency?.ttft_min_ms || 100} to{' '}
                            {config.mock_config?.latency?.ttft_max_ms || 500} ms TTFT
                          </p>
                          <p>
                            Response: {config.mock_config?.response?.min_tokens || 50} to{' '}
                            {config.mock_config?.response?.max_tokens || 500} tokens
                          </p>
                          <p>
                            Error rate: {((config.mock_config?.errors?.rate || 0) * 100).toFixed(1)}%
                          </p>
                        </div>
                      </div>

                      <div className="rounded-[1.2rem] border border-sand-deep bg-white/80 p-4">
                        <p className="text-xs font-semibold text-clay">
                          Endpoint
                        </p>
                        <code className="mt-3 block break-all rounded-xl bg-cream px-3 py-3 text-xs text-ink-soft">
                          {apiBaseUrl}
                          {providerMeta.endpoint}
                        </code>
                      </div>
                    </div>

                    <div className="flex items-center justify-between border-t border-sand-deep pt-4">
                      <span className="text-xs text-ink-mute">Created {formatDate(config.created_at)}</span>
                      <span className="text-xs font-medium text-bark">
                        Synkora proxy profile
                      </span>
                    </div>
                  </div>
                </DashboardPagePanel>
              )
            })}
          </div>
        )}
      </DashboardPageShell>

      {deleteModal.show && deleteModal.config ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
          <div className="w-full max-w-md rounded-[1.8rem] border border-sand-deep bg-white p-6 shadow-soft">
            <div className="mb-4 flex items-center gap-3">
              <div className="rounded-[1rem] bg-sand-deep p-2.5">
                <Trash2 className="h-6 w-6 text-wine" />
              </div>
              <h3 className="text-lg font-semibold text-ink">Delete Proxy Config</h3>
            </div>

            <p className="mb-6 text-sm leading-6 text-ink-soft">
              Are you sure you want to delete{' '}
              <span className="font-semibold text-ink">"{deleteModal.config.name}"</span>? Any load
              tests using this proxy will need to be reconfigured.
            </p>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteModal({ show: false, config: null })}
                disabled={deleting !== null}
                className="rounded-[0.95rem] border border-black/10 bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:bg-paper disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting !== null}
                className="inline-flex items-center gap-2 rounded-[0.95rem] bg-wine px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-wine disabled:opacity-50"
              >
                {deleting === deleteModal.config.id ? (
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
      ) : null}
    </>
  )
}
