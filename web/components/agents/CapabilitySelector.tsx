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
        <div className="motion-safe:animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="rounded-md bg-blush-wash p-4 text-sm text-danger">
        {loadError}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Presets Section */}
      {showPresets && (
        <div className="mb-6">
          <h3 className="text-sm font-medium text-ink-soft mb-3">Quick Presets</h3>
          <div className="flex flex-wrap gap-2">
            {AGENT_PRESETS.map((preset) => (
              <button
                key={preset.id}
                onClick={() => applyPreset(preset)}
                className="inline-flex items-center gap-2 px-3 py-2 bg-white border border-line rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-[color,background-color,border-color,box-shadow,opacity,transform] text-sm"
              >
                <span className="text-lg">{preset.icon}</span>
                <div className="text-left">
                  <div className="font-medium text-ink">{preset.name}</div>
                  <div className="text-xs text-ink-mute">{preset.description}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Header Actions */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-ink-soft">
          What can this agent do?
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={selectAll}
            className="text-sm text-primary-600 hover:text-primary-700 font-medium"
          >
            Select All
          </button>
          <span className="text-taupe">|</span>
          <button
            onClick={selectNone}
            className="text-sm text-ink-mute hover:text-ink-soft"
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
                className={`w-full text-left p-4 rounded-xl border-2 transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                  isSelected
                    ? 'border-primary-500 bg-primary-50 shadow-sm'
                    : isEnabled
                      ? 'border-mint bg-leaf-wash/50'
                      : 'border-line hover:border-taupe bg-white'
                }`}
              >
                {/* Icon and checkbox */}
                <div className="flex items-start justify-between mb-2">
                  <span className="text-2xl">{capability.icon}</span>
                  <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                    isSelected
                      ? 'bg-primary-500 border-primary-500'
                      : isEnabled
                        ? 'bg-leaf border-leaf'
                        : 'border-taupe bg-white'
                  }`}>
                    {(isSelected || isEnabled) && <Check className="w-3 h-3 text-white" />}
                  </div>
                </div>

                {/* Name */}
                <h4 className="font-medium text-ink text-sm mb-1">
                  {capability.name}
                </h4>

                {/* Description */}
                <p className="text-xs text-ink-mute line-clamp-2 mb-2">
                  {capability.description}
                </p>

                {/* Tool count and OAuth indicator */}
                <div className="flex items-center justify-between text-xs">
                  <span className="text-ash">
                    {capability.tool_count || capability.toolCount || capability.tools?.length || 0} tools
                    {enabledCount > 0 && !isSelected && (
                      <span className="text-leaf ml-1">
                        ({enabledCount} enabled)
                      </span>
                    )}
                  </span>
                  {hasOAuth && (
                    <span className="flex items-center gap-1 text-warn" title="Requires connection setup">
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
                  className="w-full mt-1 py-1 text-xs text-ink-mute hover:text-ink-soft flex items-center justify-center gap-1"
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
                <div className="mt-2 p-3 bg-cream rounded-lg border border-line max-h-48 overflow-y-auto">
                  <div className="space-y-1">
                    {capability.tools.map((tool: string) => (
                      <div
                        key={tool}
                        className={`text-xs px-2 py-1 rounded flex items-center gap-2 ${
                          enabledToolNames.includes(tool)
                            ? 'bg-leaf-wash text-forest'
                            : 'bg-white text-ink-soft'
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
                            <label className="text-xs font-medium text-ink-soft w-20 capitalize">
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
                                    color: 'rgb(var(--ink))',
                                    border: '1px solid #d1d5db',
                                  }}
                                >
                                  <option value="" style={{ color: 'rgb(var(--steel))' }}>Select {providerLabel} app…</option>
                                  {apps.map(app => (
                                    <option key={app.id} value={app.id} style={{ color: 'rgb(var(--ink))', backgroundColor: 'rgb(var(--white))' }}>
                                      {app.app_name} {(app.has_access_token || app.has_api_token) ? '(Connected)' : ''}
                                    </option>
                                  ))}
                                </select>
                                <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style={{ color: 'rgb(var(--steel))' }} />
                              </div>
                            ) : (
                              <div className="flex-1 flex items-center gap-2">
                                <span className="text-xs text-warn">No {providerLabel} apps configured</span>
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
                      <p className="mt-2 text-xs text-gold">
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
      <div className="mt-4 p-3 bg-cream rounded-lg border border-line">
        <div className="flex items-start gap-2">
          <Info className="w-4 h-4 text-ink-mute flex-shrink-0 mt-0.5" />
          <p className="text-xs text-ink-soft">
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
  const [collapsed, setCollapsed] = useState(false)

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
        <div className="motion-safe:animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600" />
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="rounded-md bg-blush-wash p-3 text-sm text-danger">
        {loadError}
      </div>
    )
  }

  const enabledCapabilityCount = capabilities.filter((capability) => isCapabilityEnabled(capability)).length
  const partialCapabilityCount = capabilities.filter((capability) => isCapabilityPartiallyEnabled(capability)).length
  const totalEnabledTools = capabilities.reduce((sum, capability) => {
    if (!capability.tools) return sum
    return sum + capability.tools.filter(tool => enabledToolNames.includes(tool)).length
  }, 0)

  return (
    <div className="mb-6 overflow-hidden rounded-[1.8rem] border border-black/10 bg-white shadow-soft">
      <div className="border-b border-black/10 bg-cream/90 px-5 py-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-line bg-white/80 px-3 py-1 text-[11px] font-semibold text-bark">
              <Zap className="h-3.5 w-3.5 text-leaf" />
              Quick Capability Toggles
            </div>
            <p className="mt-3 text-sm leading-6 text-ink-soft">
              Turn related tool groups on or off without editing each integration individually.
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:items-end">
            <div className="grid grid-cols-3 gap-2 sm:max-w-md">
              <div className="rounded-[1.1rem] border border-black/10 bg-white/85 px-3 py-2.5">
                <p className="text-[11px] font-semibold text-bark">Enabled</p>
                <p className="mt-1 text-lg font-semibold text-ink">{enabledCapabilityCount}</p>
              </div>
              <div className="rounded-[1.1rem] border border-line bg-sand px-3 py-2.5">
                <p className="text-[11px] font-semibold text-gold">Partial</p>
                <p className="mt-1 text-lg font-semibold text-gold">{partialCapabilityCount}</p>
              </div>
              <div className="rounded-[1.1rem] border border-leaf-wash bg-leaf-wash px-3 py-2.5">
                <p className="text-[11px] font-semibold text-leaf">Tools On</p>
                <p className="mt-1 text-lg font-semibold text-forest">{totalEnabledTools}</p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setCollapsed((prev) => !prev)}
              className="inline-flex items-center gap-2 self-start rounded-full border border-black/10 bg-white/85 px-3 py-2 text-sm font-medium text-ink-soft transition hover:bg-white sm:self-end"
            >
              {collapsed ? (
                <>
                  <ChevronDown className="h-4 w-4" />
                  Expand toggles
                </>
              ) : (
                <>
                  <ChevronUp className="h-4 w-4" />
                  Collapse toggles
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {!collapsed && (
        <div className="p-5">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {capabilities.map((capability) => {
              const isEnabled = isCapabilityEnabled(capability)
              const isPartial = isCapabilityPartiallyEnabled(capability)
              const isToggling = togglingCapability === capability.id
              const totalTools = capability.tool_count || capability.toolCount || capability.tools?.length || 0
              const enabledTools = capability.tools?.filter(tool => enabledToolNames.includes(tool)).length || 0

              return (
                <button
                  key={capability.id}
                  onClick={() => handleToggle(capability)}
                  disabled={isToggling}
                  className={`rounded-[1.35rem] border p-4 text-left transition-[color,background-color,border-color,box-shadow,opacity,transform] ${
                    isEnabled
                      ? 'border-leaf-wash bg-leaf-wash'
                      : isPartial
                        ? 'border-line bg-sand'
                        : 'border-black/10 bg-white/85 hover:border-black/20 hover:bg-white'
                  } ${isToggling ? 'cursor-wait opacity-50' : ''}`}
                  title={`${totalTools} tools`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-3">
                        <div
                          className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-[1rem] border text-lg ${
                            isEnabled
                              ? 'border-leaf-wash bg-white/70'
                              : isPartial
                                ? 'border-honey bg-white/60'
                                : 'border-black/10 bg-sand'
                          }`}
                        >
                          <span>{capability.icon}</span>
                        </div>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-ink">{capability.name}</p>
                          <p
                            className={`mt-0.5 text-xs font-semibold ${
                              isEnabled
                                ? 'text-leaf'
                                : isPartial
                                  ? 'text-gold'
                                  : 'text-bark'
                            }`}
                          >
                            {isEnabled ? 'Enabled' : isPartial ? 'Partially Enabled' : 'Disabled'}
                          </p>
                        </div>
                      </div>

                      <p className="mt-3 line-clamp-2 text-sm leading-6 text-ink-soft">
                        {capability.description}
                      </p>

                      <div className="mt-3 flex items-center justify-between gap-3 text-xs">
                        <div className="flex flex-wrap gap-2">
                          <span className="rounded-full bg-white/80 px-2.5 py-1 font-semibold text-ink-soft">
                            {totalTools} tools
                          </span>
                          {enabledTools > 0 && (
                            <span
                              className={`rounded-full px-2.5 py-1 font-semibold ${
                                isEnabled
                                  ? 'bg-white/80 text-leaf'
                                  : 'bg-white/70 text-gold'
                              }`}
                            >
                              {enabledTools} on
                            </span>
                          )}
                        </div>

                        <div
                          className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border ${
                            isEnabled
                              ? 'border-leaf bg-leaf text-white'
                              : isPartial
                                ? 'border-warn bg-sand text-gold'
                                : 'border-black/15 bg-white text-transparent'
                          }`}
                        >
                          <Check className="h-3.5 w-3.5" />
                        </div>
                      </div>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
