'use client'

import { useState, useEffect } from 'react'
import { Check, Zap, Info, AlertCircle, ChevronDown, ChevronUp, Link2, ExternalLink } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import toast from 'react-hot-toast'
import { CAPABILITIES, AGENT_PRESETS, Capability, AgentPreset } from '@/lib/data/agent-capabilities'

interface OAuthApp {
  id: number
  app_name: string  // API returns app_name, not name
  provider: string
  is_active?: boolean
  has_access_token?: boolean
  has_api_token?: boolean
}

interface CapabilitySelectorProps {
  agentId?: string
  selectedCapabilities: string[]
  onCapabilitiesChange: (capabilityIds: string[]) => void
  enabledToolNames?: string[]
  onToolsLoaded?: (tools: string[]) => void
  showPresets?: boolean
  compact?: boolean
  // New: OAuth app selection
  selectedOAuthApps?: Record<string, number>
  onOAuthAppsChange?: (oauthApps: Record<string, number>) => void
}

// Backend returns snake_case, so we define the full interface here
interface CapabilityWithTools {
  id: string
  name: string
  description: string
  icon: string
  tool_patterns: string[]
  requires_oauth?: string[]
  tools: string[]
  tool_count: number
  // Also support camelCase for frontend consistency
  toolPatterns?: string[]
  requiresOAuth?: string[]
  toolCount?: number
}

export default function CapabilitySelector({
  agentId,
  selectedCapabilities,
  onCapabilitiesChange,
  enabledToolNames = [],
  onToolsLoaded,
  showPresets = true,
  compact = false,
  selectedOAuthApps = {},
  onOAuthAppsChange
}: CapabilitySelectorProps) {
  const [capabilities, setCapabilities] = useState<CapabilityWithTools[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [expandedCapability, setExpandedCapability] = useState<string | null>(null)
  const [oauthApps, setOAuthApps] = useState<OAuthApp[]>([])
  const [loadingOAuthApps, setLoadingOAuthApps] = useState(false)

  useEffect(() => {
    loadCapabilities()
    loadOAuthApps()
  }, [])

  const loadOAuthApps = async () => {
    try {
      setLoadingOAuthApps(true)
      const apps = await apiClient.getOAuthApps()
      setOAuthApps(apps || [])
    } catch (error) {
      console.error('Failed to load OAuth apps:', error)
    } finally {
      setLoadingOAuthApps(false)
    }
  }

  // Get OAuth apps for a specific provider
  const getOAuthAppsForProvider = (provider: string) => {
    return oauthApps.filter(app => app.provider.toLowerCase() === provider.toLowerCase())
  }

  // Handle OAuth app selection
  const handleOAuthAppSelect = (provider: string, appId: number | null) => {
    if (!onOAuthAppsChange) return
    const newSelection = { ...selectedOAuthApps }
    if (appId === null) {
      delete newSelection[provider]
    } else {
      newSelection[provider] = appId
    }
    onOAuthAppsChange(newSelection)
  }

  // Get all required OAuth providers from selected capabilities
  const getRequiredOAuthProviders = () => {
    const providers = new Set<string>()
    capabilities
      .filter(c => selectedCapabilities.includes(c.id))
      .forEach(c => {
        const oauthProviders = c.requires_oauth || c.requiresOAuth || []
        oauthProviders.forEach(p => providers.add(p.toLowerCase()))
      })
    return Array.from(providers)
  }

  const loadCapabilities = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getCapabilities()
      setCapabilities(data as CapabilityWithTools[])

      // Notify parent of all available tools
      if (onToolsLoaded) {
        const allTools = data.flatMap((c: CapabilityWithTools) => c.tools || [])
        onToolsLoaded(allTools)
      }
    } catch (error) {
      console.error('Failed to load capabilities:', error)
      setLoadError('Failed to load capabilities. Please refresh the page.')
    } finally {
      setLoading(false)
    }
  }

  const toggleCapability = (capabilityId: string) => {
    const isSelected = selectedCapabilities.includes(capabilityId)
    if (isSelected) {
      onCapabilitiesChange(selectedCapabilities.filter(id => id !== capabilityId))
    } else {
      onCapabilitiesChange([...selectedCapabilities, capabilityId])
    }
  }

  const selectAll = () => {
    onCapabilitiesChange(capabilities.map(c => c.id))
  }

  const selectNone = () => {
    onCapabilitiesChange([])
  }

  const applyPreset = (preset: AgentPreset) => {
    onCapabilitiesChange(preset.capabilities)
    toast.success(`Applied "${preset.name}" preset`)
  }

  const isCapabilityEnabled = (capabilityId: string) => {
    // Check if capability is selected OR if all its tools are already enabled
    if (selectedCapabilities.includes(capabilityId)) return true

    const capability = capabilities.find(c => c.id === capabilityId)
    if (!capability || !capability.tools || capability.tools.length === 0) return false

    return capability.tools.every(tool => enabledToolNames.includes(tool))
  }

  const getEnabledToolCount = (capability: CapabilityWithTools) => {
    if (!capability.tools) return 0
    return capability.tools.filter(tool => enabledToolNames.includes(tool)).length
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
        {loadError}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Presets Section */}
      {showPresets && (
        <div className="mb-6">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Quick Presets</h3>
          <div className="flex flex-wrap gap-2">
            {AGENT_PRESETS.map((preset) => (
              <button
                key={preset.id}
                onClick={() => applyPreset(preset)}
                className="inline-flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-all text-sm"
              >
                <span className="text-lg">{preset.icon}</span>
                <div className="text-left">
                  <div className="font-medium text-gray-900">{preset.name}</div>
                  <div className="text-xs text-gray-500">{preset.description}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Header Actions */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">
          What can this agent do?
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={selectAll}
            className="text-sm text-primary-600 hover:text-primary-700 font-medium"
          >
            Select All
          </button>
          <span className="text-gray-300">|</span>
          <button
            onClick={selectNone}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Capability Grid */}
      <div className={`grid gap-3 ${compact ? 'grid-cols-2 sm:grid-cols-3' : 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4'}`}>
        {capabilities.map((capability) => {
          const isSelected = selectedCapabilities.includes(capability.id)
          const isEnabled = isCapabilityEnabled(capability.id)
          const enabledCount = getEnabledToolCount(capability)
          const oauthProviders = capability.requires_oauth || capability.requiresOAuth
          const hasOAuth = oauthProviders && oauthProviders.length > 0

          return (
            <div key={capability.id} className="relative">
              <button
                onClick={() => toggleCapability(capability.id)}
                className={`w-full text-left p-4 rounded-xl border-2 transition-all ${
                  isSelected
                    ? 'border-primary-500 bg-primary-50 shadow-sm'
                    : isEnabled
                      ? 'border-green-300 bg-green-50/50'
                      : 'border-gray-200 hover:border-gray-300 bg-white'
                }`}
              >
                {/* Icon and checkbox */}
                <div className="flex items-start justify-between mb-2">
                  <span className="text-2xl">{capability.icon}</span>
                  <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${
                    isSelected
                      ? 'bg-primary-500 border-primary-500'
                      : isEnabled
                        ? 'bg-green-500 border-green-500'
                        : 'border-gray-300 bg-white'
                  }`}>
                    {(isSelected || isEnabled) && <Check className="w-3 h-3 text-white" />}
                  </div>
                </div>

                {/* Name */}
                <h4 className="font-medium text-gray-900 text-sm mb-1">
                  {capability.name}
                </h4>

                {/* Description */}
                <p className="text-xs text-gray-500 line-clamp-2 mb-2">
                  {capability.description}
                </p>

                {/* Tool count and OAuth indicator */}
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-400">
                    {capability.tool_count || capability.toolCount || capability.tools?.length || 0} tools
                    {enabledCount > 0 && !isSelected && (
                      <span className="text-green-600 ml-1">
                        ({enabledCount} enabled)
                      </span>
                    )}
                  </span>
                  {hasOAuth && (
                    <span className="flex items-center gap-1 text-amber-600" title="Requires connection setup">
                      <AlertCircle className="w-3 h-3" />
                    </span>
                  )}
                </div>
              </button>

              {/* Expandable tool list */}
              {!compact && capability.tools && capability.tools.length > 0 && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setExpandedCapability(expandedCapability === capability.id ? null : capability.id)
                  }}
                  className="w-full mt-1 py-1 text-xs text-gray-500 hover:text-gray-700 flex items-center justify-center gap-1"
                >
                  {expandedCapability === capability.id ? (
                    <>Hide tools <ChevronUp className="w-3 h-3" /></>
                  ) : (
                    <>Show tools <ChevronDown className="w-3 h-3" /></>
                  )}
                </button>
              )}

              {/* Expanded tools list */}
              {expandedCapability === capability.id && capability.tools && (
                <div className="mt-2 p-3 bg-gray-50 rounded-lg border border-gray-200 max-h-48 overflow-y-auto">
                  <div className="space-y-1">
                    {capability.tools.map((tool: string) => (
                      <div
                        key={tool}
                        className={`text-xs px-2 py-1 rounded flex items-center gap-2 ${
                          enabledToolNames.includes(tool)
                            ? 'bg-green-100 text-green-800'
                            : 'bg-white text-gray-600'
                        }`}
                      >
                        {enabledToolNames.includes(tool) && (
                          <Check className="w-3 h-3" />
                        )}
                        <span className="truncate">
                          {tool.replace(/^internal_/, '').replace(/_/g, ' ')}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Selected summary */}
      {selectedCapabilities.length > 0 && (
        <div className="mt-4 p-4 bg-primary-50 rounded-lg border border-primary-200">
          <div className="flex items-start gap-3">
            <Zap className="w-5 h-5 text-primary-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="text-sm font-medium text-primary-900">
                {selectedCapabilities.length} capabilities selected
              </h4>
              <p className="text-xs text-primary-700 mt-1">
                {capabilities
                  .filter(c => selectedCapabilities.includes(c.id))
                  .reduce((sum, c) => sum + (c.tool_count || c.toolCount || c.tools?.length || 0), 0)} tools will be enabled
              </p>

              {/* OAuth App Selection */}
              {(() => {
                const requiredProviders = getRequiredOAuthProviders()
                if (requiredProviders.length === 0) return null

                return (
                  <div className="mt-4 pt-4 border-t border-primary-200">
                    <div className="flex items-center gap-2 mb-3">
                      <Link2 className="w-4 h-4 text-primary-600" />
                      <h5 className="text-sm font-medium text-primary-900">OAuth Connections Required</h5>
                    </div>
                    <div className="space-y-3">
                      {requiredProviders.map(provider => {
                        const apps = getOAuthAppsForProvider(provider)
                        const providerLabel = provider.charAt(0).toUpperCase() + provider.slice(1)
                        const selectedAppId = selectedOAuthApps[provider]

                        return (
                          <div key={provider} className="flex items-center gap-3">
                            <label className="text-xs font-medium text-gray-700 w-20 capitalize">
                              {providerLabel}:
                            </label>
                            {apps.length > 0 ? (
                              <div className="flex-1 relative">
                                <select
                                  value={selectedAppId || ''}
                                  onChange={(e) => handleOAuthAppSelect(provider, e.target.value ? Number(e.target.value) : null)}
                                  className="w-full text-sm rounded-lg px-3 py-2 pr-8 cursor-pointer focus:ring-2 focus:ring-primary-500 focus:outline-none"
                                  style={{
                                    backgroundColor: '#ffffff',
                                    color: '#111827',
                                    border: '1px solid #d1d5db',
                                  }}
                                >
                                  <option value="" style={{ color: '#6b7280' }}>Select {providerLabel} app...</option>
                                  {apps.map(app => (
                                    <option key={app.id} value={app.id} style={{ color: '#111827', backgroundColor: '#ffffff' }}>
                                      {app.app_name} {(app.has_access_token || app.has_api_token) ? '(Connected)' : ''}
                                    </option>
                                  ))}
                                </select>
                                <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style={{ color: '#6b7280' }} />
                              </div>
                            ) : (
                              <div className="flex-1 flex items-center gap-2">
                                <span className="text-xs text-amber-600">No {providerLabel} apps configured</span>
                                <a
                                  href="/settings/oauth-apps"
                                  target="_blank"
                                  className="text-xs text-primary-600 hover:text-primary-700 flex items-center gap-1"
                                >
                                  Configure <ExternalLink className="w-3 h-3" />
                                </a>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                    {requiredProviders.some(p => !selectedOAuthApps[p] && getOAuthAppsForProvider(p).length > 0) && (
                      <p className="mt-2 text-xs text-amber-700">
                        Select OAuth apps above to enable full functionality, or configure them later on the Tools page.
                      </p>
                    )}
                  </div>
                )
              })()}
            </div>
          </div>
        </div>
      )}

      {/* Info box */}
      <div className="mt-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
        <div className="flex items-start gap-2">
          <Info className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-gray-600">
            Capabilities group related tools together. You can fine-tune individual tools on the Tools page after creating the agent.
          </p>
        </div>
      </div>
    </div>
  )
}

// Export a simpler component for the tools page capability toggles
export function CapabilityToggles({
  agentId,
  enabledToolNames,
  onCapabilityToggle
}: {
  agentId: string
  enabledToolNames: string[]
  onCapabilityToggle: (capabilityId: string, enabled: boolean) => Promise<void>
}) {
  const [capabilities, setCapabilities] = useState<CapabilityWithTools[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [togglingCapability, setTogglingCapability] = useState<string | null>(null)

  useEffect(() => {
    loadCapabilities()
  }, [])

  const loadCapabilities = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getCapabilities()
      setCapabilities(data as CapabilityWithTools[])
    } catch (error) {
      console.error('Failed to load capabilities:', error)
      setLoadError('Failed to load capabilities. Please refresh the page.')
    } finally {
      setLoading(false)
    }
  }

  const isCapabilityEnabled = (capability: CapabilityWithTools) => {
    if (!capability.tools || capability.tools.length === 0) return false
    return capability.tools.every(tool => enabledToolNames.includes(tool))
  }

  const isCapabilityPartiallyEnabled = (capability: CapabilityWithTools) => {
    if (!capability.tools || capability.tools.length === 0) return false
    const enabledCount = capability.tools.filter(tool => enabledToolNames.includes(tool)).length
    return enabledCount > 0 && enabledCount < capability.tools.length
  }

  const handleToggle = async (capability: CapabilityWithTools) => {
    const isEnabled = isCapabilityEnabled(capability)
    setTogglingCapability(capability.id)
    try {
      await onCapabilityToggle(capability.id, !isEnabled)
    } finally {
      setTogglingCapability(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-4">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600" />
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
        {loadError}
      </div>
    )
  }

  return (
    <div className="mb-6 p-4 bg-gradient-to-r from-primary-50 to-pink-50 rounded-lg border border-primary-100">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
          <Zap className="w-4 h-4 text-primary-600" />
          Quick Capability Toggles
        </h3>
      </div>
      <div className="flex flex-wrap gap-2">
        {capabilities.map((capability) => {
          const isEnabled = isCapabilityEnabled(capability)
          const isPartial = isCapabilityPartiallyEnabled(capability)
          const isToggling = togglingCapability === capability.id

          return (
            <button
              key={capability.id}
              onClick={() => handleToggle(capability)}
              disabled={isToggling}
              className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm transition-all ${
                isEnabled
                  ? 'bg-green-100 border-green-300 text-green-800'
                  : isPartial
                    ? 'bg-amber-50 border-amber-200 text-amber-700'
                    : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300'
              } ${isToggling ? 'opacity-50 cursor-wait' : ''}`}
              title={`${capability.tool_count || capability.toolCount || capability.tools?.length || 0} tools`}
            >
              <span>{capability.icon}</span>
              <span>{capability.name}</span>
              {isEnabled && <Check className="w-3 h-3" />}
              {isPartial && !isEnabled && (
                <span className="text-xs">partial</span>
              )}
            </button>
          )
        })}
      </div>
      <p className="mt-2 text-xs text-gray-500">
        Toggle capabilities to quickly enable/disable groups of related tools
      </p>
    </div>
  )
}
