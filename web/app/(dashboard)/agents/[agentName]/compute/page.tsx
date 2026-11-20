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
  active: { dot: 'bg-leaf', badge: 'bg-leaf-wash text-forest ring-1 ring-mint', label: 'Active' },
  inactive: { dot: 'bg-ash', badge: 'bg-cream text-ink-soft ring-1 ring-line', label: 'Inactive' },
  error: { dot: 'bg-ink', badge: 'bg-blush-wash text-danger ring-1 ring-blush', label: 'Error' },
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
    'w-full rounded-[1.15rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink placeholder-ash transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint'
  const maskedCredentialsStyle = !showCredentials && credentials ? ({ WebkitTextSecurity: 'disc' } as CSSProperties) : undefined

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="mx-auto max-w-[90rem]">
        <div className="mb-4 flex flex-wrap items-center gap-1.5 text-sm">
          <Link href="/" className="flex items-center gap-1 text-ink-mute transition-colors hover:text-ink">
            <Home className="h-3.5 w-3.5" />
            Home
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-ash" />
          <Link href="/agents" className="text-ink-mute transition-colors hover:text-ink">
            Agents
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-ash" />
          <Link
            href={`/agents/${encodeURIComponent(agentName)}/view`}
            className="text-ink-mute transition-colors hover:text-ink"
          >
            {agentName}
          </Link>
          <ChevronRight className="h-3.5 w-3.5 text-ash" />
          <span className="font-medium text-ink">Compute</span>
        </div>

        <div className="bg-cream mb-6 overflow-hidden rounded-[2rem] border border-sand-deep shadow-soft">
          <div className="flex flex-col gap-5 p-6 md:p-8">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-start gap-4">
                <div className="rounded-[1.2rem] bg-sand p-3.5 shadow-soft">
                  <Server className="h-6 w-6 text-ink" />
                </div>
                <div>
                  <h1 className="text-3xl font-semibold tracking-[-0.04em] text-ink md:text-[2.4rem]">Compute</h1>
                  <p className="mt-2 text-sm leading-6 text-ink-soft">
                    Execution environment for <span className="font-semibold text-ink">{agentName}</span>.
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
          <Loader2 className="h-6 w-6 motion-safe:animate-spin text-ink" />
        </div>
      ) : (
        <div className="space-y-4">

            <AgentPagePanel className="p-5">
              <h2 className="mb-1 text-sm font-semibold text-ink">Compute Target</h2>
              <p className="mb-4 text-xs text-ink-mute">Where this agent runs commands and file operations</p>

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
                    className={`flex w-full items-start gap-3 rounded-[1.25rem] border p-4 text-left transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                      computeType === value
                        ? 'border-ink bg-white shadow-soft'
                        : 'border-black/10 bg-cream hover:border-black/20 hover:bg-white'
                    }`}
                  >
                    <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.95rem] ${
                      computeType === value ? 'bg-sand-deep' : 'bg-white'
                    }`}>
                      <Icon className={`h-4 w-4 ${computeType === value ? 'text-ink' : 'text-ink-mute'}`} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-semibold ${computeType === value ? 'text-ink' : 'text-ink'}`}>
                          {title}
                        </span>
                        {badge && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-leaf-wash text-forest">
                            {badge}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-ink-mute mt-0.5">{desc}</p>
                    </div>
                    {computeType === value && (
                      <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-leaf" />
                    )}
                  </button>
                ))}
              </div>
            </AgentPagePanel>

            {/* Platform Managed info */}
            {computeType === 'platform_managed' && (
              <AgentPagePanel className="p-5">
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.95rem] bg-leaf-wash">
                    <Settings className="h-4 w-4 text-steel" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-ink">Managed container</p>
                    <p className="text-xs text-ink-mute mt-1 leading-relaxed">
                      The platform provisions an ephemeral container for each conversation. The container image and
                      backend (Docker, Lambda, Fargate) are configured in your tenant settings.
                    </p>
                    <button
                      onClick={() => router.push('/settings/compute')}
                      className="mt-2.5 inline-flex items-center gap-1.5 text-xs font-semibold text-ink transition-colors hover:text-black"
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
                <h2 className="text-sm font-semibold text-ink">SSH Configuration</h2>

                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <label className="mb-1.5 block text-xs font-semibold text-bark">
                      Host <span className="text-plum">*</span>
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
                    <label className="mb-1.5 block text-xs font-semibold text-bark">Port</label>
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
                  <label className="mb-1.5 block text-xs font-semibold text-bark">Username</label>
                  <input
                    type="text"
                    value={remoteUser}
                    onChange={e => setRemoteUser(e.target.value)}
                    placeholder="root"
                    className={inputClass}
                  />
                </div>

                <div>
                  <label className="mb-2 block text-xs font-semibold text-bark">Authentication</label>
                  <div className="mb-3 flex gap-2">
                    {(['password', 'key'] as const).map(type => (
                      <button
                        key={type}
                        onClick={() => setAuthType(type)}
                        className={`rounded-[1rem] border px-3.5 py-2 text-xs font-semibold transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                          authType === type
                            ? 'border-ink bg-ink text-white'
                            : 'border-black/10 bg-cream text-ink-soft hover:border-black/20 hover:bg-white'
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
                        className="absolute top-2 right-2 text-ash hover:text-ink-soft transition-colors"
                      >
                        {showCredentials ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    )}
                  </div>
                  {config?.configured && (
                    <p className="mt-1 text-xs text-ash">Leave blank to keep the existing credential.</p>
                  )}
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-bark">Working Directory</label>
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
                    <label className="mb-1.5 block text-xs font-semibold text-bark">Timeout (seconds)</label>
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
                    <label className="mb-1.5 block text-xs font-semibold text-bark">Max Output (chars)</label>
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
                  <div className="flex items-start gap-2.5 rounded-[1.15rem] border border-blush-wash bg-blush-wash p-3">
                    <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-plum" />
                    <p className="text-xs text-plum">{config.error_message}</p>
                  </div>
                )}

                {config?.last_connected_at && (
                  <p className="text-xs text-ash">
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
                    className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:bg-cream disabled:opacity-50"
                  >
                    {testing ? (
                      <Loader2 className="w-4 h-4 motion-safe:animate-spin" />
                    ) : config.status === 'active' ? (
                      <Wifi className="w-4 h-4 text-leaf" />
                    ) : (
                      <WifiOff className="w-4 h-4 text-ash" />
                    )}
                    Test Connection
                  </button>
                )}
                {config?.configured && (
                  <button
                    onClick={handleRemove}
                    disabled={removing || saving}
                    className="inline-flex items-center gap-2 rounded-[1rem] border border-blush-wash bg-white px-4 py-2.5 text-sm font-semibold text-plum transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:bg-blush-wash disabled:opacity-50"
                  >
                    {removing ? <Loader2 className="w-4 h-4 motion-safe:animate-spin" /> : <Trash2 className="w-4 h-4" />}
                    Remove
                  </button>
                )}
              </div>
              <button
                onClick={handleSave}
                disabled={saving || testing}
                className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 motion-safe:animate-spin" /> : <Save className="w-4 h-4" />}
                Save
              </button>
            </div>

          </div>
        )}
      </div>
    </div>
  )
}
