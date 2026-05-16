'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { Plus, Server, Edit, Trash2, TestTube, ArrowLeft } from 'lucide-react'
import { apiClient } from '@/lib/api/http'

interface MCPServer {
  id: string
  name: string
  url: string
  description: string
  transport_type?: string
  command?: string
  args?: string[]
  env_vars?: Record<string, string>
  server_type: string
  auth_type: string
  auth_config?: any
  headers?: any
  status: string
  capabilities: any
  metadata: any
  created_at: string
  updated_at: string
}

export default function MCPServersPage() {
  const router = useRouter()
  const [servers, setServers] = useState<MCPServer[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingServer, setEditingServer] = useState<MCPServer | null>(null)

  useEffect(() => {
    fetchServers()
  }, [])

  const fetchServers = async () => {
    try {
      const { data } = await apiClient.axios.get('/api/v1/mcp/servers')
      if (data.success) {
        setServers(data.data.servers)
      }
    } catch (error) {
      console.error('Failed to fetch MCP servers:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (serverId: string) => {
    if (!confirm('Are you sure you want to delete this MCP server?')) return

    try {
      const { data } = await apiClient.axios.delete(`/api/v1/mcp/servers/${serverId}`)
      if (data.success) {
        fetchServers()
      }
    } catch (error) {
      console.error('Failed to delete server:', error)
    }
  }

  const handleTest = async (serverId: string) => {
    try {
      const { data } = await apiClient.axios.post(`/api/v1/mcp/servers/${serverId}/test`)
      if (data.success) {
        toast.success(`Connection successful! Response time: ${data.data.response_time_ms}ms`)
      }
    } catch (error) {
      console.error('Failed to test server:', error)
      toast.error('Connection test failed')
    }
  }

  return (
    <div className="dashboard-resource-page min-h-screen p-4 md:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header - More Compact */}
        <div className="mb-6">
          <button
            onClick={() => router.push('/agents')}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-3 text-sm"
          >
            <ArrowLeft size={18} />
            Back to Agents
          </button>
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">MCP Servers</h1>
              <p className="text-gray-600 mt-1 text-sm">
                Manage Model Context Protocol servers to extend agent capabilities
              </p>
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-2 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white px-5 py-2.5 rounded-lg transition-all shadow-sm hover:shadow-md text-sm font-medium"
            >
              <Plus size={18} />
              Add MCP Server
            </button>
          </div>
        </div>

        {/* Stats - More Compact */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-gray-600 text-xs font-medium">Total Servers</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">{servers.length}</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-gray-600 text-xs font-medium">Active Servers</div>
            <div className="text-2xl font-bold text-emerald-600 mt-1">
              {servers.filter(s => s.status === 'active').length}
            </div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-gray-600 text-xs font-medium">Server Types</div>
            <div className="text-2xl font-bold text-red-600 mt-1">
              {new Set(servers.map(s => s.server_type)).size}
            </div>
          </div>
        </div>

        {/* Servers List - More Compact */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-200">
            <h2 className="text-base font-semibold text-gray-900">Configured Servers</h2>
          </div>

          {loading ? (
            <div className="p-12 text-center text-gray-500 text-sm">Loading servers...</div>
          ) : servers.length === 0 ? (
            <div className="p-12 text-center">
              <Server className="mx-auto text-gray-400 mb-3" size={40} />
              <p className="text-gray-500 mb-3 text-sm">No MCP servers configured yet</p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="text-red-600 hover:text-red-700 font-medium text-sm"
              >
                Add your first MCP server
              </button>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {servers.map((server) => (
                <div key={server.id} className="p-4 hover:bg-gray-50 transition-colors">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1.5">
                        <Server className="text-red-600" size={18} />
                        <h3 className="text-base font-semibold text-gray-900">{server.name}</h3>
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            server.status === 'active'
                              ? 'bg-emerald-100 text-emerald-700'
                              : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {server.status}
                        </span>
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                          {server.server_type}
                        </span>
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                          {server.auth_type}
                        </span>
                      </div>
                      <p className="text-gray-600 mb-1.5 text-sm">{server.description}</p>
                      <div className="flex items-center gap-3 text-xs text-gray-500">
                        {server.transport_type === 'stdio' ? (
                          <span className="font-mono">{server.command} {server.args?.join(' ')}</span>
                        ) : (
                          <span className="font-mono">{server.url}</span>
                        )}
                        <span>•</span>
                        <span>Added {new Date(server.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 ml-4">
                      <button
                        onClick={() => handleTest(server.id)}
                        className="p-2 text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                        title="Test Connection"
                      >
                        <TestTube size={18} />
                      </button>
                      <button
                        onClick={() => setEditingServer(server)}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="Edit Server"
                      >
                        <Edit size={18} />
                      </button>
                      <button
                        onClick={() => handleDelete(server.id)}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="Delete Server"
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || editingServer) && (
        <MCPServerModal
          server={editingServer}
          onClose={() => {
            setShowCreateModal(false)
            setEditingServer(null)
          }}
          onSuccess={() => {
            setShowCreateModal(false)
            setEditingServer(null)
            fetchServers()
          }}
        />
      )}
    </div>
  )
}

// MCP Server Modal Component
function MCPServerModal({
  server,
  onClose,
  onSuccess,
}: {
  server: MCPServer | null
  onClose: () => void
  onSuccess: () => void
}) {
  // Get auth_config and headers from the server object directly (not from metadata)
  const serverAuthConfig = server?.auth_config || {}
  const serverHeaders = server?.headers || {}
  const serverMetadata = server?.metadata || {}
  
  const [formData, setFormData] = useState({
    name: server?.name || '',
    url: server?.url || '',
    description: server?.description || '',
    transport_type: server?.transport_type || 'http',
    command: server?.command || '',
    args: server?.args || [],
    env_vars: server?.env_vars || {},
    server_type: server?.server_type || 'http',
    auth_type: server?.auth_type || 'none',
    auth_config: serverAuthConfig,
    headers: serverHeaders,
    use_sse: serverMetadata.use_sse !== undefined ? serverMetadata.use_sse : true,
  })
  const AUTH_CONFIG_TEMPLATES: Record<string, string> = {
    api_key: JSON.stringify({ api_key: 'your_api_key_here', header_name: 'Authorization' }, null, 2),
    bearer: JSON.stringify({ token: 'your_bearer_token_here' }, null, 2),
    oauth: JSON.stringify({ client_id: 'your_client_id', client_secret: 'your_client_secret' }, null, 2),
    none: '{}',
  }

  const [authConfigJson, setAuthConfigJson] = useState(
    Object.keys(serverAuthConfig).length > 0
      ? JSON.stringify(serverAuthConfig, null, 2)
      : AUTH_CONFIG_TEMPLATES[server?.auth_type || 'none'] ?? '{}'
  )
  const [headersJson, setHeadersJson] = useState(
    JSON.stringify(serverHeaders, null, 2)
  )
  const [saving, setSaving] = useState(false)
  const fieldClass = 'w-full rounded-[1.15rem] border border-gray-200 bg-gray-50 px-4 py-4 text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500'
  const textareaClass = `${fieldClass} resize-y`
  const codeClass = 'w-full rounded-[1.15rem] border border-gray-200 bg-gray-50 px-4 py-4 font-mono text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500'
  const labelClass = 'mb-2 block text-sm font-semibold text-gray-700'
  const helpClass = 'mt-2 text-xs leading-relaxed text-gray-500'

  // Reset auth config template when auth type changes (only when creating, not editing)
  const handleAuthTypeChange = (newAuthType: string) => {
    setFormData({ ...formData, auth_type: newAuthType })
    if (!server) {
      setAuthConfigJson(AUTH_CONFIG_TEMPLATES[newAuthType] ?? '{}')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)

    try {
      // Parse JSON fields
      let authConfig = {}
      let headers = {}
      
      try {
        authConfig = authConfigJson.trim() ? JSON.parse(authConfigJson) : {}
      } catch {
        toast.error('Invalid JSON in Auth Config')
        setSaving(false)
        return
      }
      
      try {
        headers = headersJson.trim() ? JSON.parse(headersJson) : {}
      } catch {
        toast.error('Invalid JSON in Headers')
        setSaving(false)
        return
      }

      const path = server
        ? `/api/v1/mcp/servers/${server.id}`
        : `/api/v1/mcp/servers`

      const payload = {
        ...formData,
        auth_config: authConfig,
        headers: headers,
        server_metadata: {
          use_sse: formData.use_sse,
        },
      }

      const { data } = server
        ? await apiClient.axios.put(path, payload)
        : await apiClient.axios.post(path, payload)

      if (data.success) {
        toast.success(`Server ${server ? 'updated' : 'created'} successfully!`)
        onSuccess()
      } else {
        toast.error('Failed to save server: ' + data.message)
      }
    } catch (error) {
      console.error('Failed to save server:', error)
      toast.error('Failed to save server')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
      <div className="w-full max-w-2xl overflow-hidden rounded-[2rem] border border-black/10 bg-[#fcfaf5] shadow-[0_32px_90px_rgba(0,0,0,0.18)]">
        <div className="border-b border-black/10 bg-white px-8 py-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/55 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[#6e675d]">
            <Server className="h-3.5 w-3.5 text-[#2d8b69]" />
            MCP Server
          </div>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-gray-900">
            {server ? 'Edit MCP Server' : 'Add MCP Server'}
          </h2>
          <p className="mt-2 text-base text-gray-600">
            Configure your Model Context Protocol server
          </p>
        </div>

        <form onSubmit={handleSubmit} className="max-h-[calc(90vh-210px)] space-y-6 overflow-y-auto px-8 py-7">
          <div>
            <label className={labelClass}>
              Server Name *
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className={fieldClass}
              placeholder="My MCP Server"
              required
            />
          </div>

          {/* Transport Type Selector */}
          <div>
            <label className={labelClass}>
              Transport Type *
            </label>
            <select
              value={formData.transport_type}
              onChange={(e) => setFormData({ ...formData, transport_type: e.target.value })}
              className={fieldClass}
            >
              <option value="http">HTTP/SSE (Remote Server)</option>
              <option value="stdio">Stdio (Local Command)</option>
            </select>
            <p className={helpClass}>
              {formData.transport_type === 'http' 
                ? 'Connect to a remote MCP server via HTTP'
                : 'Run a local MCP server using a command (e.g., npx, python)'}
            </p>
          </div>

          {/* Conditional Fields based on transport type */}
          {formData.transport_type === 'http' ? (
            <div>
              <label className={labelClass}>
                Server URL *
              </label>
              <input
                type="url"
                value={formData.url}
                onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                className={fieldClass}
                placeholder="https://api.example.com/mcp"
                required={formData.transport_type === 'http'}
              />
              <p className={helpClass}>
                Must point to the MCP endpoint path, not just the root domain.
                Example: <span className="font-mono">https://api.example.com/mcp</span>
              </p>
            </div>
          ) : (
            <>
              {/* Command Field */}
              <div>
                <label className={labelClass}>
                  Command *
                </label>
                <input
                  type="text"
                  value={formData.command}
                  onChange={(e) => setFormData({ ...formData, command: e.target.value })}
                  className={fieldClass}
                  placeholder="npx"
                  required={formData.transport_type === 'stdio'}
                />
                <p className={helpClass}>
                  The command to execute (e.g., npx, python, node)
                </p>
              </div>

              {/* Args Field */}
              <div>
                <label className={labelClass}>
                  Arguments
                </label>
                <div className="space-y-2">
                  {formData.args.map((arg: string, index: number) => (
                    <div key={index} className="flex gap-2">
                      <input
                        type="text"
                        value={arg}
                        onChange={(e) => {
                          const newArgs = [...formData.args]
                          newArgs[index] = e.target.value
                          setFormData({ ...formData, args: newArgs })
                        }}
                        className={fieldClass}
                        placeholder="Argument"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          const newArgs = formData.args.filter((_: string, i: number) => i !== index)
                          setFormData({ ...formData, args: newArgs })
                        }}
                        className="rounded-[1rem] px-4 py-3 text-sm font-medium text-[#5b564e] transition-colors hover:bg-white"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, args: [...formData.args, ''] })}
                    className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-medium text-[#171717] transition-colors hover:bg-[#f7f2e7]"
                  >
                    + Add Argument
                  </button>
                </div>
                <p className={helpClass}>
                  Example for GitHub MCP: ["-y", "@modelcontextprotocol/server-github"]
                </p>
              </div>

              {/* Environment Variables */}
              <div>
                <label className={labelClass}>
                  Environment Variables
                </label>
                <div className="space-y-2">
                  {Object.entries(formData.env_vars).map(([key, value], index) => (
                    <div key={index} className="flex gap-2">
                      <input
                        type="text"
                        value={key}
                        onChange={(e) => {
                          const newEnvVars = { ...formData.env_vars }
                          delete newEnvVars[key]
                          newEnvVars[e.target.value] = value
                          setFormData({ ...formData, env_vars: newEnvVars })
                        }}
                        className={`${fieldClass} w-1/3`}
                        placeholder="KEY"
                      />
                      <input
                        type="text"
                        value={value}
                        onChange={(e) => {
                          const newEnvVars = { ...formData.env_vars }
                          newEnvVars[key] = e.target.value
                          setFormData({ ...formData, env_vars: newEnvVars })
                        }}
                        className={`flex-1 ${fieldClass}`}
                        placeholder="value"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          const newEnvVars = { ...formData.env_vars }
                          delete newEnvVars[key]
                          setFormData({ ...formData, env_vars: newEnvVars })
                        }}
                        className="rounded-[1rem] px-4 py-3 text-sm font-medium text-[#5b564e] transition-colors hover:bg-white"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() => {
                      const newEnvVars = { ...formData.env_vars }
                      newEnvVars[''] = ''
                      setFormData({ ...formData, env_vars: newEnvVars })
                    }}
                    className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-medium text-[#171717] transition-colors hover:bg-[#f7f2e7]"
                  >
                    + Add Environment Variable
                  </button>
                </div>
                <p className={helpClass}>
                  Example: GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxxxx
                </p>
              </div>
            </>
          )}

          <div>
            <label className={labelClass}>
              Description *
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className={textareaClass}
              rows={3}
              placeholder="Describe what this MCP server provides..."
              required
            />
          </div>

          {/* Only show auth and server type for HTTP transport */}
          {formData.transport_type === 'http' && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>
                  Server Type
                </label>
                <select
                  value={formData.server_type}
                  onChange={(e) => setFormData({ ...formData, server_type: e.target.value })}
                  className={fieldClass}
                >
                  <option value="http">HTTP</option>
                  <option value="websocket">WebSocket</option>
                  <option value="grpc">gRPC</option>
                </select>
              </div>

              <div>
                <label className={labelClass}>
                  Authentication
                </label>
                <select
                  value={formData.auth_type}
                  onChange={(e) => handleAuthTypeChange(e.target.value)}
                  className={fieldClass}
                >
                  <option value="none">None</option>
                  <option value="api_key">API Key</option>
                  <option value="bearer">Bearer Token</option>
                  <option value="oauth">OAuth</option>
                </select>
              </div>
            </div>
          )}

          {/* Auth Config - Show when auth_type is not 'none' and transport is HTTP */}
          {formData.transport_type === 'http' && formData.auth_type !== 'none' && (
            <div>
              <label className={labelClass}>
                Auth Config (JSON)
              </label>
              <textarea
                value={authConfigJson}
                onChange={(e) => setAuthConfigJson(e.target.value)}
                className={codeClass}
                rows={5}
              />
              {formData.auth_type === 'api_key' && (
                <div className="mt-3 rounded-[1.15rem] border border-black/10 bg-[#eef6ff] p-4 text-xs text-[#294a7c] space-y-1.5">
                  <p className="font-semibold">API Key fields:</p>
                  <p><span className="font-mono font-bold">api_key</span> — your actual API key value</p>
                  <p><span className="font-mono font-bold">header_name</span> — the HTTP header to send it in</p>
                  <p className="mt-1.5 font-semibold">Common header names:</p>
                  <p><span className="font-mono">Authorization</span> — use this when the server expects <span className="font-mono">Authorization: your_key</span></p>
                  <p><span className="font-mono">X-API-Key</span> — used by many REST APIs</p>
                </div>
              )}
              {formData.auth_type === 'bearer' && (
                <div className="mt-3 rounded-[1.15rem] border border-black/10 bg-[#eef6ff] p-4 text-xs text-[#294a7c] space-y-1.5">
                  <p className="font-semibold">Bearer Token fields:</p>
                  <p><span className="font-mono font-bold">token</span> — your bearer token (sent as <span className="font-mono">Authorization: Bearer &lt;token&gt;</span>)</p>
                  <p className="mt-1 text-[#45638f]">Use this for GitHub, PostHog personal API keys, and most OAuth2 APIs.</p>
                </div>
              )}
              {formData.auth_type === 'oauth' && (
                <div className="mt-3 rounded-[1.15rem] border border-black/10 bg-[#eef6ff] p-4 text-xs text-[#294a7c] space-y-1.5">
                  <p className="font-semibold">OAuth fields:</p>
                  <p><span className="font-mono font-bold">client_id</span> — OAuth application client ID</p>
                  <p><span className="font-mono font-bold">client_secret</span> — OAuth application client secret</p>
                </div>
              )}
            </div>
          )}

          {/* Headers - Only for HTTP transport */}
          {formData.transport_type === 'http' && (
            <div>
              <label className={labelClass}>
                Custom Headers (JSON) - Optional
              </label>
              <textarea
                value={headersJson}
                onChange={(e) => setHeadersJson(e.target.value)}
                className={codeClass}
                rows={4}
                placeholder={`{\n  "X-Project-ID": "your_project_id"\n}`}
              />
              <p className={helpClass}>
                Extra HTTP headers the server requires — for example a project ID or API version header.
                Do not put your auth credentials here; use the Auth Config above instead.
              </p>
            </div>
          )}

          {/* Use SSE Toggle - Only for HTTP transport */}
          {formData.transport_type === 'http' && (
            <div className="flex items-center justify-between rounded-[1.25rem] border border-black/10 bg-[#f7f2e7] p-4">
              <div className="flex-1 pr-4">
                <label className="mb-1 block text-sm font-semibold text-gray-700">
                  Use Server-Sent Events (SSE)
                </label>
                <p className="text-xs text-gray-500">
                  Enable SSE for streaming responses. Disable for servers that only support POST requests (e.g., GitHub MCP).
                </p>
              </div>
              <label className="relative inline-flex cursor-pointer items-center">
                <input
                  type="checkbox"
                  checked={formData.use_sse}
                  onChange={(e) => setFormData({ ...formData, use_sse: e.target.checked })}
                  className="peer sr-only"
                />
                <div className="relative h-6 w-11 rounded-full bg-black/10 transition-colors peer-checked:bg-[#181818] after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-white after:bg-white after:transition-transform peer-checked:after:translate-x-full" />
              </label>
            </div>
          )}

          <div className="rounded-[1.25rem] border border-black/10 bg-[rgba(99,223,190,0.16)] p-4">
            <h4 className="mb-1 text-sm font-semibold text-[#171717]">About MCP Servers</h4>
            <p className="text-xs leading-relaxed text-[#4f645c]">
              MCP (Model Context Protocol) servers provide additional tools and resources that your agents can use.
              They extend agent capabilities beyond built-in tools by connecting to external APIs, databases, or services.
            </p>
          </div>
        </form>

        {/* Fixed Footer with Buttons */}
        <div className="flex justify-end gap-3 border-t border-black/10 bg-[#f7f2e7] px-8 py-5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-[1.15rem] border border-black/10 bg-white px-5 py-3 text-sm font-medium text-[#5b564e] transition-colors hover:bg-[#fffdf8]"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            onClick={(e) => {
              e.preventDefault()
              const form = e.currentTarget.closest('div')?.previousElementSibling as HTMLFormElement
              form?.requestSubmit()
            }}
            className="rounded-[1.15rem] bg-[#181818] px-6 py-3 text-sm font-semibold uppercase tracking-[0.12em] text-[#f7f2e7] transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? 'Saving...' : server ? 'Update Server' : 'Create Server'}
          </button>
        </div>
      </div>
    </div>
  )
}
