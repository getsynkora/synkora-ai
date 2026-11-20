'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Server, Plus } from 'lucide-react'
import toast from 'react-hot-toast'
import LoadingSpinner from '@/components/common/LoadingSpinner'
import ErrorAlert from '@/components/common/ErrorAlert'
import EmptyState from '@/components/common/EmptyState'
import { apiClient } from '@/lib/api/client'
import AgentPageShell from '@/components/agents/AgentPageShell'

interface Agent {
  id: string
  name: string
  type: string
}

interface MCPServer {
  id: number
  name: string
  description: string
  url: string
  auth_type: string
  is_active: boolean
  created_at: string
  updated_at: string
}

interface AgentMCPServer {
  id: string
  name: string
  description: string
  url: string
  auth_type: string
  is_active: boolean
  mcp_config: {
    enabled_tools?: string[]
    timeout?: number
    max_retries?: number
    tool_config?: Record<string, any>
  }
  created_at: string
  updated_at: string
}

interface MCPTool {
  name: string
  description: string
  inputSchema: any
}

const warmModalFieldClass =
  'w-full rounded-[1rem] border border-black/10 bg-cream px-4 py-3 text-sm text-ink transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-mint'
const warmModalLabelClass = 'mb-2 block text-sm font-semibold text-ink'
const warmModalHelpClass = 'mt-1.5 text-xs leading-5 text-ink-mute'

export default function AgentMCPServersPage() {
  const params = useParams()
  const agentName = params.agentName as string

  const [agent, setAgent] = useState<Agent | null>(null)
  const [attachedServers, setAttachedServers] = useState<AgentMCPServer[]>([])
  const [availableServers, setAvailableServers] = useState<MCPServer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAttachModal, setShowAttachModal] = useState(false)
  const [showToolsModal, setShowToolsModal] = useState(false)
  const [showManageToolsModal, setShowManageToolsModal] = useState(false)
  const [selectedServerId, setSelectedServerId] = useState<string | null>(null)
  const [selectedServerTools, setSelectedServerTools] = useState<MCPTool[]>([])
  const [loadingTools, setLoadingTools] = useState(false)
  const [savingTools, setSavingTools] = useState(false)
  const [toolSearch, setToolSearch] = useState('')
  const [expandedTools, setExpandedTools] = useState<Set<string>>(new Set())
  const [attachConfig, setAttachConfig] = useState({
    enabled_tools: [] as string[],
    timeout: 30,
    max_retries: 3,
  })
  const [manageToolsConfig, setManageToolsConfig] = useState<{
    enabled_tools: string[]
    timeout: number
    max_retries: number
  }>({
    enabled_tools: [],
    timeout: 30,
    max_retries: 3,
  })

  useEffect(() => {
    fetchAgent()
    fetchAvailableServers()
  }, [agentName])

  useEffect(() => {
    if (agent) {
      fetchAttachedServers()
    }
  }, [agent])

  const fetchAgent = async () => {
    try {
      const data = await apiClient.getAgent(agentName)
      setAgent({
        id: data.id,
        name: data.agent_name,
        type: data.agent_type
      })
    } catch (err) {
      console.error('Failed to fetch agent:', err)
    }
  }

  const fetchAttachedServers = async () => {
    if (!agent) return
    
    try {
      setLoading(true)
      const data = await apiClient.getAgentMCPServers(agent.id)
      const servers = Array.isArray(data) ? data : ((data as any)?.mcp_servers || [])
      setAttachedServers(servers)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  const fetchAvailableServers = async () => {
    try {
      const data = await apiClient.getMCPServers()
      const servers = Array.isArray(data) ? data : ((data as any)?.servers || (data as any)?.data?.servers || [])
      const mappedServers = servers.map((server: any) => ({
        ...server,
        is_active: server.status?.toUpperCase() === 'ACTIVE'
      }))
      setAvailableServers(mappedServers)
    } catch (err) {
      console.error('Failed to fetch MCP servers:', err)
    }
  }

  const fetchServerTools = async (serverId: string) => {
    if (!agent) return

    try {
      setLoadingTools(true)
      const response = await apiClient.getMCPServerTools(agent.id, serverId)

      // Check if the response indicates a failure (success: false)
      if (response && response.success === false) {
        toast.error(response.message || 'Failed to connect to MCP server')
        setSelectedServerTools([])
        return
      }

      const tools = response?.data?.tools || []
      setSelectedServerTools(tools)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to fetch tools')
      setSelectedServerTools([])
    } finally {
      setLoadingTools(false)
    }
  }

  const handleAttach = async () => {
    if (!agent || !selectedServerId) return

    try {
      await apiClient.addMCPServerToAgent(agent.id, {
        mcp_server_id: selectedServerId,
        mcp_config: attachConfig,
      })

      setShowAttachModal(false)
      setSelectedServerId(null)
      setAttachConfig({
        enabled_tools: [],
        timeout: 30,
        max_retries: 3,
      })
      fetchAttachedServers()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to attach MCP server')
    }
  }

  const handleDetach = async (serverId: string, serverName: string) => {
    if (!agent) return
    
    if (!confirm(`Are you sure you want to detach "${serverName}" from this agent?`)) {
      return
    }

    try {
      await apiClient.removeMCPServerFromAgent(agent.id, serverId)
      fetchAttachedServers()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to detach MCP server')
    }
  }

  const handleViewTools = async (serverId: string) => {
    setSelectedServerId(serverId)
    setShowToolsModal(true)
    await fetchServerTools(serverId)
  }

  const handleManageTools = async (serverId: string, currentConfig: AgentMCPServer['mcp_config']) => {
    setSelectedServerId(serverId)
    setManageToolsConfig({
      enabled_tools: currentConfig.enabled_tools || [],
      timeout: currentConfig.timeout || 30,
      max_retries: currentConfig.max_retries || 3,
    })
    setShowManageToolsModal(true)
    await fetchServerTools(serverId)
  }

  const handleToggleTool = (toolName: string) => {
    setManageToolsConfig(prev => {
      const enabled = prev.enabled_tools.includes(toolName)
      if (enabled) {
        // Remove tool
        return {
          ...prev,
          enabled_tools: prev.enabled_tools.filter(t => t !== toolName)
        }
      } else {
        // Add tool
        return {
          ...prev,
          enabled_tools: [...prev.enabled_tools, toolName]
        }
      }
    })
  }

  const handleToggleAllTools = () => {
    if (manageToolsConfig.enabled_tools.length === selectedServerTools.length) {
      // Deselect all
      setManageToolsConfig(prev => ({ ...prev, enabled_tools: [] }))
    } else {
      // Select all
      setManageToolsConfig(prev => ({
        ...prev,
        enabled_tools: selectedServerTools.map(t => t.name)
      }))
    }
  }

  const handleSaveToolConfig = async () => {
    if (!agent || !selectedServerId) return

    try {
      setSavingTools(true)
      await apiClient.updateMCPServerConfig(agent.id, selectedServerId, manageToolsConfig)

      setShowManageToolsModal(false)
      setSelectedServerId(null)
      setSelectedServerTools([])
      fetchAttachedServers()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save configuration')
    } finally {
      setSavingTools(false)
    }
  }

  const getAuthTypeBadgeColor = (authType: string) => {
    const colors: Record<string, string> = {
      'api_key': 'bg-blush-wash text-wine',
      'bearer': 'bg-blush-wash text-wine',
      'oauth': 'bg-leaf-wash text-forest',
      'none': 'bg-sand text-ink',
    }
    return colors[authType.toLowerCase()] || 'bg-sand text-ink'
  }

  const getUnattachedServers = () => {
    const attachedIds = attachedServers.map(s => s.id)
    return availableServers.filter(s => !attachedIds.includes(String(s.id)))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="MCP Servers"
      description={<>Configure which MCP servers <span className="font-semibold text-ink">{agent?.name || agentName}</span> can access for extended tool capabilities.</>}
      icon={Server}
      backHref={`/agents/${agentName}/view`}
      backLabel="Back to Agent"
      badge="External Tooling"
      actions={
        <button
          onClick={() => setShowAttachModal(true)}
          disabled={getUnattachedServers().length === 0}
          className="inline-flex items-center gap-2 rounded-[1rem] bg-ink px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus className="w-4 h-4" />
          Attach MCP Server
        </button>
      }
    >

      {error && (
        <div className="mb-6">
          <ErrorAlert message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      {/* Attached MCP Servers */}
      {attachedServers.length === 0 ? (
        <EmptyState
          icon={
            <svg aria-hidden="true"
              className="mx-auto h-10 w-10 text-hotpink"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"
              />
            </svg>
          }
          title="No MCP servers attached"
          description="Attach an MCP server to extend this agent's capabilities with additional tools."
          actionLabel={getUnattachedServers().length > 0 ? "Attach MCP Server" : undefined}
          onAction={getUnattachedServers().length > 0 ? () => setShowAttachModal(true) : undefined}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {attachedServers.map((server) => (
            <div
              key={server.id}
              className="bg-white rounded-xl border border-line p-4 hover:shadow-md hover:border-blush transition-[color,background-color,border-color,box-shadow,opacity,transform] flex flex-col"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${server.is_active ? 'bg-leaf' : 'bg-taupe'}`} title={server.is_active ? 'Active' : 'Inactive'} />
                  <h3 className="text-sm font-semibold text-ink truncate">
                    {server.name}
                  </h3>
                </div>
                <span className={`ml-2 flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${getAuthTypeBadgeColor(server.auth_type)}`}>
                  {server.auth_type}
                </span>
              </div>

              {/* Description */}
              <p className="text-xs text-ink-mute line-clamp-2 mb-2">
                {server.description}
              </p>

              {/* URL */}
              <p className="text-[10px] text-ash font-mono truncate mb-3">{server.url}</p>

              {/* Config Stats */}
              <div className="flex items-center gap-3 text-[10px] text-ink-mute mb-3 pb-3 border-b border-sand">
                <span>Timeout: <span className="text-ink-soft font-medium">{server.mcp_config.timeout || 30}s</span></span>
                <span>Retries: <span className="text-ink-soft font-medium">{server.mcp_config.max_retries || 3}</span></span>
                {server.mcp_config.enabled_tools && server.mcp_config.enabled_tools.length > 0 && (
                  <span>Tools: <span className="text-ink-soft font-medium">{server.mcp_config.enabled_tools.length}</span></span>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 mt-auto">
                <button
                  onClick={() => handleViewTools(server.id)}
                  className="flex-1 px-2 py-1.5 text-[11px] font-medium text-leaf bg-blush-wash rounded-lg hover:bg-blush-wash transition-colors"
                >
                  View Tools
                </button>
                <button
                  onClick={() => handleManageTools(server.id, server.mcp_config)}
                  className="flex-1 px-2 py-1.5 text-[11px] font-medium text-leaf bg-blush-wash rounded-lg hover:bg-blush-wash transition-colors"
                >
                  Manage
                </button>
                <button
                  onClick={() => handleDetach(server.id, server.name)}
                  className="px-2 py-1.5 text-[11px] font-medium text-ink-mute hover:text-leaf hover:bg-blush-wash rounded-lg transition-colors"
                  title="Detach server"
                >
                  <svg aria-hidden="true" className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Attach Modal */}
      {showAttachModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4">
          <div className="max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-[1.7rem] border border-line bg-cream shadow-soft">
            <div className="flex items-start justify-between border-b border-sand-deep px-5 py-5 sm:px-6">
              <div>
                <p className="text-[11px] font-semibold text-clay">
                  External Tooling
                </p>
                <h2 className="mt-1 text-[1.9rem] font-semibold tracking-[-0.04em] text-ink">
                  Attach MCP Server
                </h2>
              </div>
              <button
                onClick={() => {
                  setShowAttachModal(false)
                  setSelectedServerId(null)
                }}
                className="rounded-full p-2 text-ash transition-colors hover:bg-white/80 hover:text-ink-soft"
              >
                <svg aria-hidden="true" className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-5 px-5 py-5 sm:px-6">
              {/* Select MCP Server */}
              <div className="space-y-2.5">
                <label className={warmModalLabelClass}>
                  Select MCP Server
                </label>
                <div className="max-h-64 space-y-2.5 overflow-y-auto">
                  {getUnattachedServers().map((server) => (
                    <button
                      key={server.id}
                      onClick={() => setSelectedServerId(String(server.id))}
                      className={`w-full rounded-[1.15rem] border text-left transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                        selectedServerId === String(server.id)
                          ? 'border-tan bg-cream shadow-soft'
                          : 'border-line bg-white/75 hover:border-line hover:bg-cream'
                      }`}
                    >
                      <div className="flex items-start gap-3 px-4 py-3.5">
                        <div className="mt-0.5 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-[1rem] bg-sand-deep">
                          <Server className="h-4.5 w-4.5 text-ink" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <h3 className="truncate text-sm font-semibold text-ink">{server.name}</h3>
                              <p className="mt-1 text-sm text-ink-soft">{server.description}</p>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${getAuthTypeBadgeColor(server.auth_type)}`}>
                                {server.auth_type}
                              </span>
                              <span
                                className={`h-2.5 w-2.5 rounded-full ${server.is_active ? 'bg-leaf' : 'bg-taupe'}`}
                                title={server.is_active ? 'Active' : 'Inactive'}
                              />
                            </div>
                          </div>
                          <p className="mt-2 truncate font-mono text-xs text-clay">{server.url}</p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* MCP Configuration */}
              {selectedServerId && (
                <div className="space-y-4 rounded-[1.3rem] border border-line bg-white/55 p-4">
                  <div>
                    <h3 className="text-sm font-semibold text-ink">MCP Configuration</h3>
                    <p className="mt-1 text-xs text-ink-mute">
                      Configure default behavior for this server when attached to the agent.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className={warmModalLabelClass}>
                        Timeout (seconds)
                      </label>
                      <input
                        type="number"
                        value={attachConfig.timeout}
                        onChange={(e) => setAttachConfig({ ...attachConfig, timeout: parseInt(e.target.value) })}
                        className={warmModalFieldClass}
                        min="1"
                        max="300"
                      />
                      <p className={warmModalHelpClass}>
                        Request timeout in seconds.
                      </p>
                    </div>

                    <div>
                      <label className={warmModalLabelClass}>
                        Max Retries
                      </label>
                      <input
                        type="number"
                        value={attachConfig.max_retries}
                        onChange={(e) => setAttachConfig({ ...attachConfig, max_retries: parseInt(e.target.value) })}
                        className={warmModalFieldClass}
                        min="0"
                        max="10"
                      />
                      <p className={warmModalHelpClass}>
                        Retry attempts before failing.
                      </p>
                    </div>
                  </div>

                  <div>
                    <label className={warmModalLabelClass}>
                      Enabled Tools (Optional)
                    </label>
                    <input
                      type="text"
                      placeholder="Leave empty to enable all tools"
                      value={attachConfig.enabled_tools.join(', ')}
                      onChange={(e) => setAttachConfig({
                        ...attachConfig,
                        enabled_tools: e.target.value ? e.target.value.split(',').map(t => t.trim()) : []
                      })}
                      className={warmModalFieldClass}
                    />
                    <p className={warmModalHelpClass}>
                      Use a comma-separated list, or leave blank to allow all tools.
                    </p>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex flex-col-reverse gap-3 border-t border-line pt-4 sm:flex-row sm:items-center">
                <button
                  onClick={() => {
                    setShowAttachModal(false)
                    setSelectedServerId(null)
                  }}
                  className="inline-flex min-w-[8rem] items-center justify-center rounded-[1rem] border border-line bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:bg-cream"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAttach}
                  disabled={!selectedServerId}
                  className="inline-flex flex-1 items-center justify-center rounded-[1rem] bg-ink px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Attach MCP Server
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tools Modal */}
      {showToolsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4">
          <div className="flex max-h-[88vh] w-full max-w-3xl flex-col rounded-[1.7rem] border border-line bg-cream shadow-soft">
            {/* Header */}
            <div className="flex flex-shrink-0 items-start justify-between border-b border-sand-deep px-5 py-5 sm:px-6">
              <div>
                <p className="text-[11px] font-semibold text-clay">
                  MCP Server
                </p>
                <h2 className="mt-1 text-[1.9rem] font-semibold tracking-[-0.04em] text-ink">
                  Available Tools
                </h2>
                {!loadingTools && selectedServerTools.length > 0 && (
                  <p className="mt-0.5 text-sm text-clay">
                    {selectedServerTools.length} tool{selectedServerTools.length !== 1 ? 's' : ''} available
                  </p>
                )}
              </div>
              <button
                onClick={() => {
                  setShowToolsModal(false)
                  setSelectedServerId(null)
                  setSelectedServerTools([])
                  setToolSearch('')
                  setExpandedTools(new Set())
                }}
                className="rounded-full p-2 text-ash transition-colors hover:bg-white/80 hover:text-ink-soft"
              >
                <svg aria-hidden="true" className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Search */}
            {!loadingTools && selectedServerTools.length > 0 && (
              <div className="flex-shrink-0 px-5 pt-4 sm:px-6">
                <div className="relative">
                  <svg aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-taupe" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input
                    type="text"
                    placeholder="Search tools…"
                    value={toolSearch}
                    onChange={(e) => setToolSearch(e.target.value)}
                    className="w-full rounded-[1rem] border border-line bg-white/70 py-2.5 pl-9 pr-4 text-sm text-ink placeholder-taupe transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-tan"
                  />
                </div>
              </div>
            )}

            {/* Tool list */}
            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 sm:px-6">
              {loadingTools ? (
                <div className="flex items-center justify-center py-16">
                  <LoadingSpinner size="lg" />
                </div>
              ) : selectedServerTools.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-sand-deep">
                    <svg aria-hidden="true" className="h-6 w-6 text-tan" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                    </svg>
                  </div>
                  <p className="mt-4 text-sm font-semibold text-ink">No tools available</p>
                  <p className="mt-1 text-xs text-clay">This MCP server doesn't provide any tools or failed to connect.</p>
                </div>
              ) : (() => {
                const filtered = selectedServerTools.filter(t =>
                  !toolSearch || t.name.toLowerCase().includes(toolSearch.toLowerCase()) || t.description?.toLowerCase().includes(toolSearch.toLowerCase())
                )
                if (filtered.length === 0) return (
                  <div className="py-10 text-center text-sm text-clay">No tools match &ldquo;{toolSearch}&rdquo;</div>
                )
                return (
                  <div className="space-y-2">
                    {filtered.map((tool) => {
                      const hasParams = tool.inputSchema?.properties && Object.keys(tool.inputSchema.properties).length > 0
                      const isExpanded = expandedTools.has(tool.name)
                      const requiredParams = tool.inputSchema?.required || []
                      return (
                        <div
                          key={tool.name}
                          className="overflow-hidden rounded-[1.15rem] border border-line bg-white/60 transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:border-paper-dim"
                        >
                          {/* Tool header row */}
                          <div className="flex items-center gap-3 px-4 py-3">
                            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[0.65rem] bg-sand-deep">
                              <svg aria-hidden="true" className="h-3.5 w-3.5 text-clay" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              </svg>
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-sm font-semibold text-ink">{tool.name}</span>
                                {hasParams && (
                                  <span className="rounded-full bg-sand-deep px-2 py-0.5 text-[10px] font-semibold text-clay">
                                    {Object.keys(tool.inputSchema.properties).length} param{Object.keys(tool.inputSchema.properties).length !== 1 ? 's' : ''}
                                  </span>
                                )}
                              </div>
                              {tool.description && (
                                <p className="mt-0.5 text-xs leading-relaxed text-ink-soft line-clamp-2">{tool.description}</p>
                              )}
                            </div>
                            {hasParams && (
                              <button
                                onClick={() => setExpandedTools(prev => {
                                  const next = new Set(prev)
                                  if (next.has(tool.name)) next.delete(tool.name)
                                  else next.add(tool.name)
                                  return next
                                })}
                                className="ml-2 flex-shrink-0 rounded-full p-1.5 text-clay transition-colors hover:bg-sand-deep hover:text-bark"
                                title={isExpanded ? 'Collapse parameters' : 'Expand parameters'}
                              >
                                <svg aria-hidden="true" className={`h-4 w-4 transition-transform motion-reduce:transition-none ${isExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                              </button>
                            )}
                          </div>

                          {/* Expandable params */}
                          {hasParams && isExpanded && (
                            <div className="border-t border-sand-deep bg-cream px-4 py-3">
                              <p className="mb-2 text-[10px] font-semibold text-clay">Parameters</p>
                              <div className="space-y-2">
                                {Object.entries(tool.inputSchema.properties).map(([key, val]: [string, any]) => {
                                  const isRequired = requiredParams.includes(key)
                                  return (
                                    <div key={key} className="flex items-start gap-2.5">
                                      <div className="flex items-center gap-1.5 pt-0.5">
                                        <span className="font-mono text-xs font-semibold text-rust">{key}</span>
                                        <span className="rounded bg-sand px-1.5 py-0.5 text-[10px] text-ink-mute">{val.type || 'any'}</span>
                                        {isRequired && (
                                          <span className="rounded bg-sand-deep px-1.5 py-0.5 text-[10px] font-semibold text-rust">required</span>
                                        )}
                                      </div>
                                      {val.description && (
                                        <p className="text-xs text-ink-mute leading-relaxed">{val.description}</p>
                                      )}
                                    </div>
                                  )
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )
              })()}
            </div>

            {/* Footer */}
            <div className="flex-shrink-0 border-t border-line px-5 py-4 sm:px-6">
              <button
                onClick={() => {
                  setShowToolsModal(false)
                  setSelectedServerId(null)
                  setSelectedServerTools([])
                  setToolSearch('')
                  setExpandedTools(new Set())
                }}
                className="inline-flex w-full items-center justify-center rounded-[1rem] border border-line bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:bg-cream"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manage Tools Modal */}
      {showManageToolsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4">
          <div className="flex max-h-[88vh] w-full max-w-3xl flex-col rounded-[1.7rem] border border-line bg-cream shadow-soft">
            {/* Header */}
            <div className="flex flex-shrink-0 items-start justify-between border-b border-sand-deep px-5 py-5 sm:px-6">
              <div>
                <p className="text-[11px] font-semibold text-clay">
                  MCP Server
                </p>
                <h2 className="mt-1 text-[1.9rem] font-semibold tracking-[-0.04em] text-ink">
                  Manage Tools
                </h2>
                {!loadingTools && selectedServerTools.length > 0 && (
                  <p className="mt-0.5 text-sm text-clay">
                    {manageToolsConfig.enabled_tools.length === 0
                      ? 'All tools enabled by default'
                      : `${manageToolsConfig.enabled_tools.length} of ${selectedServerTools.length} tools enabled`}
                  </p>
                )}
              </div>
              <button
                onClick={() => {
                  setShowManageToolsModal(false)
                  setSelectedServerId(null)
                  setSelectedServerTools([])
                }}
                className="rounded-full p-2 text-ash transition-colors hover:bg-white/80 hover:text-ink-soft"
              >
                <svg aria-hidden="true" className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {loadingTools ? (
              <div className="flex flex-1 items-center justify-center py-16">
                <LoadingSpinner size="lg" />
              </div>
            ) : (
              <>
                {/* Scrollable body */}
                <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6 space-y-5">

                  {/* Configuration row */}
                  <div className="rounded-[1.3rem] border border-line bg-white/55 p-4">
                    <h3 className="mb-3 text-sm font-semibold text-ink">Connection Settings</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="mb-1.5 block text-xs font-semibold text-ink-soft">
                          Timeout (seconds)
                        </label>
                        <input
                          type="number"
                          value={manageToolsConfig.timeout}
                          onChange={(e) => setManageToolsConfig({ ...manageToolsConfig, timeout: parseInt(e.target.value) })}
                          className="w-full rounded-[1rem] border border-black/10 bg-cream px-4 py-2.5 text-sm text-ink transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-tan"
                          min="1"
                          max="300"
                        />
                      </div>
                      <div>
                        <label className="mb-1.5 block text-xs font-semibold text-ink-soft">
                          Max Retries
                        </label>
                        <input
                          type="number"
                          value={manageToolsConfig.max_retries}
                          onChange={(e) => setManageToolsConfig({ ...manageToolsConfig, max_retries: parseInt(e.target.value) })}
                          className="w-full rounded-[1rem] border border-black/10 bg-cream px-4 py-2.5 text-sm text-ink transition-[color,background-color,border-color,box-shadow,opacity,transform] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-tan"
                          min="0"
                          max="10"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Tools selection */}
                  <div>
                    <div className="mb-3 flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-semibold text-ink">Enabled Tools</h3>
                        <p className="mt-0.5 text-xs text-clay">
                          {manageToolsConfig.enabled_tools.length === 0
                            ? 'All tools will be available to the agent.'
                            : 'Only checked tools will be available to the agent.'}
                        </p>
                      </div>
                      {selectedServerTools.length > 0 && (
                        <button
                          onClick={handleToggleAllTools}
                          className="rounded-[0.75rem] border border-line bg-white/70 px-3 py-1.5 text-xs font-semibold text-bark transition-colors hover:bg-sand"
                        >
                          {manageToolsConfig.enabled_tools.length === selectedServerTools.length ? 'Deselect All' : 'Select All'}
                        </button>
                      )}
                    </div>

                    {selectedServerTools.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-10 text-center">
                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-sand-deep">
                          <svg aria-hidden="true" className="h-5 w-5 text-tan" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                          </svg>
                        </div>
                        <p className="mt-3 text-sm font-semibold text-ink">No tools available</p>
                        <p className="mt-1 text-xs text-clay">This MCP server doesn't provide any tools or failed to connect.</p>
                      </div>
                    ) : (
                      <div className="space-y-1.5">
                        {selectedServerTools.map((tool) => {
                          const checked = manageToolsConfig.enabled_tools.includes(tool.name)
                          const paramCount = tool.inputSchema?.properties ? Object.keys(tool.inputSchema.properties).length : 0
                          return (
                            <label
                              key={tool.name}
                              className={`flex cursor-pointer items-center gap-3 rounded-[1.1rem] border px-4 py-3 transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                                checked
                                  ? 'border-tan bg-cream shadow-soft'
                                  : 'border-line bg-white/50 hover:border-paper-dim hover:bg-white/70'
                              }`}
                            >
                              {/* Custom checkbox */}
                              <div className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-[0.4rem] border-2 transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                                checked
                                  ? 'border-rust bg-rust'
                                  : 'border-tan bg-white/80'
                              }`}>
                                {checked && (
                                  <svg aria-hidden="true" className="h-3 w-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                  </svg>
                                )}
                              </div>
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => handleToggleTool(tool.name)}
                                className="sr-only"
                              />
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-mono text-sm font-semibold text-ink">{tool.name}</span>
                                  {paramCount > 0 && (
                                    <span className="rounded-full bg-sand-deep px-2 py-0.5 text-[10px] font-semibold text-clay">
                                      {paramCount}p
                                    </span>
                                  )}
                                </div>
                                {tool.description && (
                                  <p className="mt-0.5 text-xs text-ink-mute line-clamp-1">{tool.description}</p>
                                )}
                              </div>
                            </label>
                          )
                        })}
                      </div>
                    )}
                  </div>
                </div>

                {/* Footer actions */}
                <div className="flex flex-shrink-0 flex-col-reverse gap-3 border-t border-line px-5 py-4 sm:flex-row sm:items-center sm:px-6">
                  <button
                    onClick={() => {
                      setShowManageToolsModal(false)
                      setSelectedServerId(null)
                      setSelectedServerTools([])
                    }}
                    disabled={savingTools}
                    className="inline-flex min-w-[8rem] items-center justify-center rounded-[1rem] border border-line bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:bg-cream disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveToolConfig}
                    disabled={savingTools}
                    className="inline-flex flex-1 items-center justify-center gap-2 rounded-[1rem] bg-ink px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {savingTools ? (
                      <>
                        <LoadingSpinner size="sm" />
                        Saving…
                      </>
                    ) : (
                      'Save Configuration'
                    )}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </AgentPageShell>
  )
}
