'use client'

import { useState, useEffect, type CSSProperties } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import {
  Server,
  Save,
  Loader2,
  CheckCircle,
  XCircle,
  Wifi,
  WifiOff,
  Trash2,
  Eye,
  EyeOff,
  Box,
  Settings,
  ExternalLink,
  ChevronRight,
  Home,
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import { AgentPagePanel } from '@/components/agents/AgentPageShell'

type ComputeType = 'platform_managed' | 'remote_server' | 'local'
type ComputeStatus = 'active' | 'inactive' | 'error'
type AuthType = 'password' | 'key'

interface ComputeConfig {
  configured: boolean
  compute_type: ComputeType
  status?: ComputeStatus
  remote_host?: string
  remote_port?: number
  remote_user?: string
  remote_auth_type?: AuthType
  remote_base_path?: string
  timeout_seconds?: number
  max_output_chars?: number
  last_connected_at?: string
  error_message?: string
}

const STATUS_STYLES: Record<ComputeStatus, { dot: string; badge: string; label: string }> = {
  active: { dot: 'bg-emerald-500', badge: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200', label: 'Active' },
  inactive: { dot: 'bg-gray-400', badge: 'bg-gray-50 text-gray-600 ring-1 ring-gray-200', label: 'Inactive' },
  error: { dot: 'bg-red-500', badge: 'bg-red-50 text-red-700 ring-1 ring-red-200', label: 'Error' },
}

export default function AgentComputePage() {
  const params = useParams()
  const router = useRouter()
  const agentName = decodeURIComponent((params?.agentName as string) || '')

  const [agentId, setAgentId] = useState<string | null>(null)
  const [config, setConfig] = useState<ComputeConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [showCredentials, setShowCredentials] = useState(false)

  const [computeType, setComputeType] = useState<ComputeType>('platform_managed')
  const [remoteHost, setRemoteHost] = useState('')
  const [remotePort, setRemotePort] = useState('22')
  const [remoteUser, setRemoteUser] = useState('root')
  const [authType, setAuthType] = useState<AuthType>('password')
  const [credentials, setCredentials] = useState('')
  const [basePath, setBasePath] = useState('/tmp/agent_workspace')
  const [timeoutSecs, setTimeoutSecs] = useState('300')
  const [maxOutput, setMaxOutput] = useState('8000')

  useEffect(() => {
    loadConfig()
  }, [agentName])

  const loadConfig = async (resolvedId?: string) => {
    try {
      setLoading(true)
      const id = resolvedId ?? agentId
      if (!id) {
        const agent = await apiClient.getAgent(agentName)
        setAgentId(agent.id)
        return loadConfig(agent.id)
      }
      const data: ComputeConfig = await apiClient.request('GET', `/api/v1/agents/${id}/compute`)
      setConfig(data)
      if (data.configured) {
        setComputeType(data.compute_type)
        if (data.compute_type === 'remote_server') {
          setRemoteHost(data.remote_host || '')
          setRemotePort(String(data.remote_port || 22))
          setRemoteUser(data.remote_user || 'root')
          setAuthType((data.remote_auth_type as AuthType) || 'password')
          setBasePath(data.remote_base_path || '/tmp/agent_workspace')
          setTimeoutSecs(String(data.timeout_seconds || 300))
          setMaxOutput(String(data.max_output_chars || 8000))
        }
      }
    } catch {
      toast.error('Failed to load compute configuration')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (computeType === 'remote_server' && !remoteHost.trim()) {
      toast.error('Remote host is required')
      return
    }
    if (!agentId) return
    setSaving(true)
    try {
      const body: Record<string, unknown> = {
        compute_type: computeType,
        remote_host: computeType === 'remote_server' ? remoteHost.trim() : undefined,
        remote_port: computeType === 'remote_server' ? parseInt(remotePort, 10) : undefined,
        remote_user: computeType === 'remote_server' ? remoteUser.trim() : undefined,
        remote_auth_type: computeType === 'remote_server' ? authType : undefined,
        remote_credentials: computeType === 'remote_server' && credentials.trim() ? credentials : undefined,
        remote_base_path: computeType === 'remote_server' ? basePath.trim() : undefined,
        timeout_seconds: parseInt(timeoutSecs, 10),
        max_output_chars: parseInt(maxOutput, 10),
      }
      const data: ComputeConfig = await apiClient.request('POST', `/api/v1/agents/${agentId}/compute`, body)
      setConfig(data)
      setCredentials('')
      toast.success('Compute configuration saved')
    } catch {
      toast.error('Failed to save compute configuration')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    if (!agentId) return
    setTesting(true)
    try {
      const data = await apiClient.request('POST', `/api/v1/agents/${agentId}/compute/test`)
      if (data.success) {
        toast.success(`Connection successful (${data.latency_ms ?? '?'}ms)`)
        await loadConfig()
      } else {
        toast.error(data.error || 'Test failed')
      }
    } catch {
      toast.error('Test failed')
    } finally {
      setTesting(false)
    }
  }

  const handleRemove = async () => {
    if (!confirm('Remove compute configuration? The agent will revert to platform managed.')) return
    if (!agentId) return
    setRemoving(true)
    try {
      await apiClient.request('DELETE', `/api/v1/agents/${agentId}/compute`)
      setConfig({ configured: false, compute_type: 'platform_managed' })
      setComputeType('platform_managed')
      setRemoteHost('')
      setCredentials('')
      toast.success('Compute configuration removed')
    } catch {
      toast.error('Failed to remove compute configuration')
    } finally {
      setRemoving(false)
    }
  }

  const statusInfo = config?.status ? STATUS_STYLES[config.status] : null

  const inputClass =
    'w-full rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-4 py-3 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]'
  const maskedCredentialsStyle = !showCredentials && credentials ? ({ WebkitTextSecurity: 'disc' } as CSSProperties) : undefined

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="mx-auto max-w-[90rem]">
        <div className="mb-4 flex flex-wrap items-center gap-1.5 text-sm">
          <Link href="/" className="flex items-center gap-1 text-gray-500 transition-colors hover:text-[#171717]">
            <Home className="h-3.5 w-3.5" />
            Home
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-gray-400" />
          <Link href="/agents" className="text-gray-500 transition-colors hover:text-[#171717]">
            Agents
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-gray-400" />
          <Link
            href={`/agents/${encodeURIComponent(agentName)}/view`}
            className="text-gray-500 transition-colors hover:text-[#171717]"
          >
            {agentName}
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-gray-400" />
          <span className="font-medium text-gray-900">Compute</span>
        </div>

        <div className="mb-6 overflow-hidden rounded-[2rem] border border-[#eadfce] bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.96),_rgba(247,240,231,0.94)_50%,_rgba(237,230,220,0.92)_100%)] shadow-[0_28px_80px_-42px_rgba(88,63,39,0.32)]">
          <div className="flex flex-col gap-5 p-6 md:p-8">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-start gap-4">
                <div className="rounded-[1.2rem] bg-[#f3ecde] p-3.5 shadow-[0_16px_30px_-24px_rgba(74,49,22,0.3)]">
                  <Server className="h-6 w-6 text-[#171717]" />
                </div>
                <div>
                  <h1 className="text-3xl font-semibold tracking-[-0.04em] text-gray-950 md:text-[2.4rem]">Compute</h1>
                  <p className="mt-2 text-sm leading-6 text-gray-600">
                    Execution environment for <span className="font-semibold text-gray-900">{agentName}</span>.
                  </p>
                </div>
              </div>
              {statusInfo && (
                <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold ${statusInfo.badge}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${statusInfo.dot}`} />
                  {statusInfo.label}
                </span>
              )}
            </div>
          </div>
        </div>

        {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-[#171717]" />
        </div>
      ) : (
        <div className="space-y-4">

            <AgentPagePanel className="p-5">
              <h2 className="mb-1 text-sm font-semibold text-gray-900">Compute Target</h2>
              <p className="mb-4 text-xs text-gray-500">Where this agent runs commands and file operations</p>

              <div className="space-y-2">
                {([
                  {
                    value: 'platform_managed' as const,
                    icon: Box,
                    title: 'Platform Managed',
                    desc: 'Isolated container provisioned automatically per conversation.',
                    badge: 'Recommended',
                  },
                  {
                    value: 'remote_server' as const,
                    icon: Server,
                    title: 'Remote Server',
                    desc: 'Execute on your own machine via SSH.',
                    badge: null,
                  },
                ]).map(({ value, icon: Icon, title, desc, badge }) => (
                  <button
                    key={value}
                    onClick={() => setComputeType(value)}
                    className={`flex w-full items-start gap-3 rounded-[1.25rem] border p-4 text-left transition-all ${
                      computeType === value
                        ? 'border-[#171717] bg-white shadow-[0_18px_40px_rgba(0,0,0,0.08)]'
                        : 'border-black/10 bg-[#fcfaf5] hover:border-black/20 hover:bg-white'
                    }`}
                  >
                    <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.95rem] ${
                      computeType === value ? 'bg-[#f1eadc]' : 'bg-white'
                    }`}>
                      <Icon className={`h-4 w-4 ${computeType === value ? 'text-[#171717]' : 'text-gray-500'}`} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-semibold ${computeType === value ? 'text-gray-950' : 'text-gray-800'}`}>
                          {title}
                        </span>
                        {badge && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-700">
                            {badge}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
                    </div>
                    {computeType === value && (
                      <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                    )}
                  </button>
                ))}
              </div>
            </AgentPagePanel>

            {/* Platform Managed info */}
            {computeType === 'platform_managed' && (
              <AgentPagePanel className="p-5">
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.95rem] bg-[#edf4f6]">
                    <Settings className="h-4 w-4 text-[#486c77]" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">Managed container</p>
                    <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                      The platform provisions an ephemeral container for each conversation. The container image and
                      backend (Docker, Lambda, Fargate) are configured in your tenant settings.
                    </p>
                    <button
                      onClick={() => router.push('/settings/compute')}
                      className="mt-2.5 inline-flex items-center gap-1.5 text-xs font-semibold text-[#171717] transition-colors hover:text-black"
                    >
                      <ExternalLink className="w-3 h-3" />
                      Configure tenant compute backend
                    </button>
                  </div>
                </div>
              </AgentPagePanel>
            )}

            {/* SSH Configuration */}
            {computeType === 'remote_server' && (
              <AgentPagePanel className="space-y-4 p-5">
                <h2 className="text-sm font-semibold text-gray-900">SSH Configuration</h2>

                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <label className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.18em] text-[#7c5d45]">
                      Host <span className="text-[#8b5a74]">*</span>
                    </label>
                    <input
                      type="text"
                      value={remoteHost}
                      onChange={e => setRemoteHost(e.target.value)}
                      placeholder="192.168.1.100 or server.example.com"
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.18em] text-[#7c5d45]">Port</label>
                    <input
                      type="number"
                      value={remotePort}
                      onChange={e => setRemotePort(e.target.value)}
                      min={1}
                      max={65535}
                      className={inputClass}
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.18em] text-[#7c5d45]">Username</label>
                  <input
                    type="text"
                    value={remoteUser}
                    onChange={e => setRemoteUser(e.target.value)}
                    placeholder="root"
                    className={inputClass}
                  />
                </div>

                <div>
                  <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-[#7c5d45]">Authentication</label>
                  <div className="mb-3 flex gap-2">
                    {(['password', 'key'] as const).map(type => (
                      <button
                        key={type}
                        onClick={() => setAuthType(type)}
                        className={`rounded-[1rem] border px-3.5 py-2 text-xs font-semibold transition-all ${
                          authType === type
                            ? 'border-[#171717] bg-[#171717] text-white'
                            : 'border-black/10 bg-[#fcfaf5] text-gray-600 hover:border-black/20 hover:bg-white'
                        }`}
                      >
                        {type === 'password' ? 'Password' : 'SSH Key'}
                      </button>
                    ))}
                  </div>
                  <div className="relative">
                    <textarea
                      value={credentials}
                      onChange={e => setCredentials(e.target.value)}
                      placeholder={
                        authType === 'password'
                          ? 'Enter password (leave blank to keep existing)'
                          : 'Paste private key (-----BEGIN ... KEY-----)\nLeave blank to keep existing'
                      }
                      rows={authType === 'key' ? 5 : 1}
                      className={`${inputClass} resize-none font-mono`}
                      style={maskedCredentialsStyle}
                    />
                    {credentials && (
                      <button
                        type="button"
                        onClick={() => setShowCredentials(v => !v)}
                        className="absolute top-2 right-2 text-gray-400 hover:text-gray-600 transition-colors"
                      >
                        {showCredentials ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    )}
                  </div>
                  {config?.configured && (
                    <p className="mt-1 text-xs text-gray-400">Leave blank to keep the existing credential.</p>
                  )}
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.18em] text-[#7c5d45]">Working Directory</label>
                  <input
                    type="text"
                    value={basePath}
                    onChange={e => setBasePath(e.target.value)}
                    placeholder="/tmp/agent_workspace"
                    className={`${inputClass} font-mono`}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.18em] text-[#7c5d45]">Timeout (seconds)</label>
                    <input
                      type="number"
                      value={timeoutSecs}
                      onChange={e => setTimeoutSecs(e.target.value)}
                      min={10}
                      max={3600}
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.18em] text-[#7c5d45]">Max Output (chars)</label>
                    <input
                      type="number"
                      value={maxOutput}
                      onChange={e => setMaxOutput(e.target.value)}
                      min={1000}
                      max={100000}
                      className={inputClass}
                    />
                  </div>
                </div>

                {config?.error_message && (
                  <div className="flex items-start gap-2.5 rounded-[1.15rem] border border-[#ead8e1] bg-[#f8ecef] p-3">
                    <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#8b5a74]" />
                    <p className="text-xs text-[#8b5a74]">{config.error_message}</p>
                  </div>
                )}

                {config?.last_connected_at && (
                  <p className="text-xs text-gray-400">
                    Last connected: {new Date(config.last_connected_at).toLocaleString()}
                  </p>
                )}
              </AgentPagePanel>
            )}

            {/* Actions */}
            <div className="flex items-center justify-between gap-3 pt-1">
              <div className="flex items-center gap-2">
                {config?.configured && computeType === 'remote_server' && (
                  <button
                    onClick={handleTest}
                    disabled={testing || saving}
                    className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-white px-4 py-2.5 text-sm font-semibold text-gray-700 transition-all hover:bg-[#fcfaf5] disabled:opacity-50"
                  >
                    {testing ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : config.status === 'active' ? (
                      <Wifi className="w-4 h-4 text-emerald-500" />
                    ) : (
                      <WifiOff className="w-4 h-4 text-gray-400" />
                    )}
                    Test Connection
                  </button>
                )}
                {config?.configured && (
                  <button
                    onClick={handleRemove}
                    disabled={removing || saving}
                    className="inline-flex items-center gap-2 rounded-[1rem] border border-[#ead8e1] bg-white px-4 py-2.5 text-sm font-semibold text-[#8b5a74] transition-all hover:bg-[#f8ecef] disabled:opacity-50"
                  >
                    {removing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                    Remove
                  </button>
                )}
              </div>
              <button
                onClick={handleSave}
                disabled={saving || testing}
                className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save
              </button>
            </div>

          </div>
        )}
      </div>
    </div>
  )
}
