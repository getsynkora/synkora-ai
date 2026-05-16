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
  'w-full rounded-[1rem] border border-black/10 bg-[#fcfaf5] px-4 py-3 text-sm text-gray-900 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]'
const warmModalLabelClass = 'mb-2 block text-sm font-semibold text-gray-800'
const warmModalHelpClass = 'mt-1.5 text-xs leading-5 text-gray-500'

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
      'api_key': 'bg-red-100 text-red-800',
      'bearer': 'bg-purple-100 text-purple-800',
      'oauth': 'bg-emerald-100 text-emerald-800',
      'none': 'bg-gray-100 text-gray-800',
    }
    return colors[authType.toLowerCase()] || 'bg-gray-100 text-gray-800'
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
      description={<>Configure which MCP servers <span className="font-semibold text-gray-900">{agent?.name || agentName}</span> can access for extended tool capabilities.</>}
      icon={Server}
      backHref={`/agents/${agentName}/view`}
      backLabel="Back to Agent"
      badge="External Tooling"
      actions={
        <button
          onClick={() => setShowAttachModal(true)}
          disabled={getUnattachedServers().length === 0}
          className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
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
            <svg
              className="mx-auto h-10 w-10 text-red-400"
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
              className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md hover:border-red-300 transition-all flex flex-col"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${server.is_active ? 'bg-emerald-500' : 'bg-gray-300'}`} title={server.is_active ? 'Active' : 'Inactive'} />
                  <h3 className="text-sm font-semibold text-gray-900 truncate">
                    {server.name}
                  </h3>
                </div>
                <span className={`ml-2 flex-shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${getAuthTypeBadgeColor(server.auth_type)}`}>
                  {server.auth_type}
                </span>
              </div>

              {/* Description */}
              <p className="text-xs text-gray-500 line-clamp-2 mb-2">
                {server.description}
              </p>

              {/* URL */}
              <p className="text-[10px] text-gray-400 font-mono truncate mb-3">{server.url}</p>

              {/* Config Stats */}
              <div className="flex items-center gap-3 text-[10px] text-gray-500 mb-3 pb-3 border-b border-gray-100">
                <span>Timeout: <span className="text-gray-700 font-medium">{server.mcp_config.timeout || 30}s</span></span>
                <span>Retries: <span className="text-gray-700 font-medium">{server.mcp_config.max_retries || 3}</span></span>
                {server.mcp_config.enabled_tools && server.mcp_config.enabled_tools.length > 0 && (
                  <span>Tools: <span className="text-gray-700 font-medium">{server.mcp_config.enabled_tools.length}</span></span>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 mt-auto">
                <button
                  onClick={() => handleViewTools(server.id)}
                  className="flex-1 px-2 py-1.5 text-[11px] font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors"
                >
                  View Tools
                </button>
                <button
                  onClick={() => handleManageTools(server.id, server.mcp_config)}
                  className="flex-1 px-2 py-1.5 text-[11px] font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors"
                >
                  Manage
                </button>
                <button
                  onClick={() => handleDetach(server.id, server.name)}
                  className="px-2 py-1.5 text-[11px] font-medium text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  title="Detach server"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(28,22,16,0.28)] p-4 backdrop-blur-[8px]">
          <div className="max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-[1.7rem] border border-[#ddd3c5] bg-[linear-gradient(180deg,_rgba(250,247,241,0.98),_rgba(241,236,229,0.98))] shadow-[0_36px_96px_-40px_rgba(17,14,10,0.45)]">
            <div className="flex items-start justify-between border-b border-[#e7ded2] px-5 py-5 sm:px-6">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#8d6c51]">
                  External Tooling
                </p>
                <h2 className="mt-1 text-[1.9rem] font-semibold tracking-[-0.04em] text-gray-950">
                  Attach MCP Server
                </h2>
              </div>
              <button
                onClick={() => {
                  setShowAttachModal(false)
                  setSelectedServerId(null)
                }}
                className="rounded-full p-2 text-[#9a8f81] transition-colors hover:bg-white/80 hover:text-[#5f564c]"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
                      className={`w-full rounded-[1.15rem] border text-left transition-all ${
                        selectedServerId === String(server.id)
                          ? 'border-[#d7b8a3] bg-[linear-gradient(180deg,_rgba(252,245,238,0.98),_rgba(247,239,231,0.98))] shadow-[0_14px_36px_-28px_rgba(135,85,42,0.35)]'
                          : 'border-[#e6ddd1] bg-white/75 hover:border-[#dccab6] hover:bg-[#fcfaf5]'
                      }`}
                    >
                      <div className="flex items-start gap-3 px-4 py-3.5">
                        <div className="mt-0.5 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-[1rem] bg-[#f1eadc]">
                          <Server className="h-4.5 w-4.5 text-[#171717]" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <h3 className="truncate text-sm font-semibold text-gray-900">{server.name}</h3>
                              <p className="mt-1 text-sm text-gray-600">{server.description}</p>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${getAuthTypeBadgeColor(server.auth_type)}`}>
                                {server.auth_type}
                              </span>
                              <span
                                className={`h-2.5 w-2.5 rounded-full ${server.is_active ? 'bg-emerald-500' : 'bg-gray-300'}`}
                                title={server.is_active ? 'Active' : 'Inactive'}
                              />
                            </div>
                          </div>
                          <p className="mt-2 truncate font-mono text-xs text-[#8b7760]">{server.url}</p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* MCP Configuration */}
              {selectedServerId && (
                <div className="space-y-4 rounded-[1.3rem] border border-[#e4dbcf] bg-white/55 p-4">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900">MCP Configuration</h3>
                    <p className="mt-1 text-xs text-gray-500">
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
              <div className="flex flex-col-reverse gap-3 border-t border-[#e6ddd2] pt-4 sm:flex-row sm:items-center">
                <button
                  onClick={() => {
                    setShowAttachModal(false)
                    setSelectedServerId(null)
                  }}
                  className="inline-flex min-w-[8rem] items-center justify-center rounded-[1rem] border border-[#ddd7ce] bg-white px-4 py-2.5 text-sm font-semibold text-[#5f564c] transition-colors hover:bg-[#fcfaf5]"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAttach}
                  disabled={!selectedServerId}
                  className="inline-flex flex-1 items-center justify-center rounded-[1rem] bg-[#171717] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50"
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
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-6 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-5">
              <h2 className="text-xl font-bold text-gray-900">Available Tools</h2>
              <button
                onClick={() => {
                  setShowToolsModal(false)
                  setSelectedServerId(null)
                  setSelectedServerTools([])
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {loadingTools ? (
              <div className="flex items-center justify-center py-12">
                <LoadingSpinner size="lg" />
              </div>
            ) : selectedServerTools.length === 0 ? (
              <EmptyState
                icon={
                  <svg
                    className="mx-auto h-10 w-10 text-red-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
                    />
                  </svg>
                }
                title="No tools available"
                description="This MCP server doesn't provide any tools or failed to connect."
              />
            ) : (
              <div className="space-y-3">
                {selectedServerTools.map((tool, index) => (
                  <div
                    key={index}
                    className="border border-gray-200 rounded-lg p-4 hover:border-red-300 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="text-base font-semibold text-gray-900">{tool.name}</h3>
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                        Tool
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 mb-2">{tool.description}</p>
                    
                    {tool.inputSchema && tool.inputSchema.properties && (
                      <div className="bg-red-50 rounded p-3">
                        <p className="text-xs font-medium text-gray-700 mb-2">Parameters:</p>
                        <div className="space-y-1">
                          {Object.entries(tool.inputSchema.properties).map(([key, value]: [string, any]) => (
                            <div key={key} className="text-xs">
                              <span className="font-mono text-red-600">{key}</span>
                              <span className="text-gray-500"> ({value.type})</span>
                              {tool.inputSchema.required?.includes(key) && (
                                <span className="ml-1 text-red-500">*</span>
                              )}
                              {value.description && (
                                <p className="text-gray-600 ml-4 mt-0.5">{value.description}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div className="mt-5">
              <button
                onClick={() => {
                  setShowToolsModal(false)
                  setSelectedServerId(null)
                  setSelectedServerTools([])
                }}
                className="w-full px-5 py-2.5 border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-red-50 hover:border-red-300 transition-colors font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manage Tools Modal */}
      {showManageToolsModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-6 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-5">
              <h2 className="text-xl font-bold text-gray-900">Manage Tools</h2>
              <button
                onClick={() => {
                  setShowManageToolsModal(false)
                  setSelectedServerId(null)
                  setSelectedServerTools([])
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {loadingTools ? (
              <div className="flex items-center justify-center py-12">
                <LoadingSpinner size="lg" />
              </div>
            ) : (
              <>
                {/* Configuration Section */}
                <div className="mb-5 space-y-3">
                  <h3 className="text-base font-semibold text-gray-900">Configuration</h3>
                  
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Timeout (seconds)
                      </label>
                      <input
                        type="number"
                        value={manageToolsConfig.timeout}
                        onChange={(e) => setManageToolsConfig({ ...manageToolsConfig, timeout: parseInt(e.target.value) })}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                        min="1"
                        max="300"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Max Retries
                      </label>
                      <input
                        type="number"
                        value={manageToolsConfig.max_retries}
                        onChange={(e) => setManageToolsConfig({ ...manageToolsConfig, max_retries: parseInt(e.target.value) })}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                        min="0"
                        max="10"
                      />
                    </div>
                  </div>
                </div>

                {/* Tools Selection */}
                <div className="mb-5">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="text-base font-semibold text-gray-900">
                      Select Tools ({manageToolsConfig.enabled_tools.length} of {selectedServerTools.length} enabled)
                    </h3>
                    <button
                      onClick={handleToggleAllTools}
                      className="px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors"
                    >
                      {manageToolsConfig.enabled_tools.length === selectedServerTools.length ? 'Deselect All' : 'Select All'}
                    </button>
                  </div>

                  <p className="text-xs text-gray-600 mb-3">
                    {manageToolsConfig.enabled_tools.length === 0 
                      ? 'No tools selected. All tools will be available by default.' 
                      : 'Only selected tools will be available to the agent.'}
                  </p>

                  {selectedServerTools.length === 0 ? (
                    <EmptyState
                      icon={
                        <svg
                          className="mx-auto h-10 w-10 text-red-400"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
                          />
                        </svg>
                      }
                      title="No tools available"
                      description="This MCP server doesn't provide any tools or failed to connect."
                    />
                  ) : (
                    <div className="space-y-2">
                      {selectedServerTools.map((tool) => (
                        <label
                          key={tool.name}
                          className="flex items-start p-3 border border-gray-200 rounded-lg hover:bg-red-50 hover:border-red-200 cursor-pointer transition-colors"
                        >
                          <input
                            type="checkbox"
                            checked={manageToolsConfig.enabled_tools.includes(tool.name)}
                            onChange={() => handleToggleTool(tool.name)}
                            className="mt-1 h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300 rounded"
                          />
                          <div className="ml-3 flex-1">
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-medium text-gray-900">{tool.name}</span>
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                                Tool
                              </span>
                            </div>
                            <p className="text-xs text-gray-600 mt-1">{tool.description}</p>
                            {tool.inputSchema && tool.inputSchema.properties && (
                              <div className="mt-1 text-xs text-gray-500">
                                Parameters: {Object.keys(tool.inputSchema.properties).join(', ')}
                              </div>
                            )}
                          </div>
                        </label>
                      ))}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex gap-3 pt-5 border-t border-gray-200">
                  <button
                    onClick={handleSaveToolConfig}
                    disabled={savingTools}
                    className="flex-1 px-5 py-2.5 bg-gradient-to-r from-red-500 to-red-600 text-white text-sm rounded-lg hover:from-red-600 hover:to-red-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2 shadow-sm"
                  >
                    {savingTools ? (
                      <>
                        <LoadingSpinner size="sm" />
                        Saving...
                      </>
                    ) : (
                      'Save Configuration'
                    )}
                  </button>
                  <button
                    onClick={() => {
                      setShowManageToolsModal(false)
                      setSelectedServerId(null)
                      setSelectedServerTools([])
                    }}
                    disabled={savingTools}
                    className="px-5 py-2.5 border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-red-50 hover:border-red-300 transition-colors font-medium disabled:opacity-50"
                  >
                    Cancel
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
