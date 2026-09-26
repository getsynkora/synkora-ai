'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import {
  AgentLLMConfig,
  JevRoutingConfig,
  JevTier,
  JEV_TIERS,
  RoutingMode,
  ROUTING_MODE_LABELS,
  ROUTING_MODE_DESCRIPTIONS,
} from '@/types/agent-llm-config'

interface RoutingModePanelProps {
  agentName: string
  currentMode: RoutingMode
  routingConfig?: Record<string, any>
  configs?: AgentLLMConfig[]
  onSave: (mode: RoutingMode, config: Record<string, any>) => Promise<void>
}

const MODE_ICONS: Record<RoutingMode, string> = {
  fixed: '🔒',
  round_robin: '⚖️',
  cost_opt: '💰',
  intent: '🎯',
  latency_opt: '⚡',
  jev: '🧠',
}

// Exported as default; import as: import RoutingModePanel from '@/components/agents/llm-configs/RoutingModePanel'
export default function RoutingModePanel({
  agentName,
  currentMode,
  routingConfig = {},
  configs = [],
  onSave,
}: RoutingModePanelProps) {
  const [selectedMode, setSelectedMode] = useState<RoutingMode>(currentMode)
  const [qualityFloor, setQualityFloor] = useState<number>(
    routingConfig.quality_floor ?? 0.5
  )
  const savedJev: JevRoutingConfig = routingConfig.jev ?? {}
  const [jevModelRouting, setJevModelRouting] = useState<boolean>(
    savedJev.features?.model_routing ?? true
  )
  const [jevToolFiltering, setJevToolFiltering] = useState<boolean>(
    savedJev.features?.tool_filtering ?? true
  )
  const [jevTierMap, setJevTierMap] = useState<Partial<Record<JevTier, string>>>(
    savedJev.model_tier_map ?? {}
  )
  const [jevThreshold, setJevThreshold] = useState<'yes' | 'unclear'>(
    savedJev.tool_filtering_threshold ?? 'yes'
  )
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // The agent loads asynchronously (and after each save), so resync local state from props.
  useEffect(() => {
    const jev: JevRoutingConfig = routingConfig.jev ?? {}
    setSelectedMode(currentMode)
    setQualityFloor(routingConfig.quality_floor ?? 0.5)
    setJevModelRouting(jev.features?.model_routing ?? true)
    setJevToolFiltering(jev.features?.tool_filtering ?? true)
    setJevTierMap(jev.model_tier_map ?? {})
    setJevThreshold(jev.tool_filtering_threshold ?? 'yes')
  }, [currentMode, routingConfig])

  const modes: RoutingMode[] = ['fixed', 'cost_opt', 'intent', 'latency_opt', 'round_robin', 'jev']
  const enabledConfigs = configs.filter((c) => c.enabled)

  // Build the jev block, keeping keys the UI doesn't edit (e.g. a custom "model").
  const buildJev = (): JevRoutingConfig => {
    const tierMap: Partial<Record<JevTier, string>> = {}
    for (const { value } of JEV_TIERS) {
      const id = jevTierMap[value]
      if (id && enabledConfigs.some((c) => c.id === id)) tierMap[value] = id
    }
    return {
      ...savedJev,
      features: { model_routing: jevModelRouting, tool_filtering: jevToolFiltering },
      model_tier_map: tierMap,
      tool_filtering_threshold: jevThreshold,
    }
  }

  const jevInvalid = selectedMode === 'jev' && !jevModelRouting && !jevToolFiltering
  const jevChanged =
    selectedMode === 'jev' && JSON.stringify(buildJev()) !== JSON.stringify(savedJev)

  const hasChanges =
    selectedMode !== currentMode ||
    (selectedMode === 'cost_opt' && qualityFloor !== (routingConfig.quality_floor ?? 0.5)) ||
    jevChanged

  const handleSave = async () => {
    setIsSaving(true)
    try {
      // Start from the stored config so switching modes doesn't discard other modes' settings
      // (the API replaces routing_config wholesale).
      const config: Record<string, any> = { ...routingConfig }
      if (selectedMode === 'cost_opt') {
        config.quality_floor = qualityFloor
      }
      if (selectedMode === 'jev') {
        config.jev = buildJev()
      }
      await onSave(selectedMode, config)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-gray-900">Model Routing</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Control how requests are distributed across your configured models to reduce cost
          </p>
        </div>
        {hasChanges && (
          <button
            onClick={handleSave}
            disabled={isSaving || jevInvalid}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
          >
            {isSaving ? (
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : saved ? (
              '✓ Saved'
            ) : (
              'Save Routing'
            )}
          </button>
        )}
        {!hasChanges && saved && (
          <span className="text-sm text-green-600 font-medium">✓ Saved</span>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {modes.map((mode) => {
          const isSelected = selectedMode === mode
          return (
            <button
              key={mode}
              onClick={() => setSelectedMode(mode)}
              className={`relative text-left p-4 rounded-lg border-2 transition-all ${
                isSelected
                  ? 'border-red-500 bg-red-50'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              }`}
            >
              {isSelected && (
                <span className="absolute top-2 right-2 w-4 h-4 rounded-full bg-red-500 flex items-center justify-center">
                  <svg className="w-2.5 h-2.5 text-white" fill="currentColor" viewBox="0 0 12 12">
                    <path d="M10 3L5 8.5 2 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                  </svg>
                </span>
              )}
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-lg">{MODE_ICONS[mode]}</span>
                <span className={`text-sm font-semibold ${isSelected ? 'text-red-700' : 'text-gray-800'}`}>
                  {ROUTING_MODE_LABELS[mode]}
                </span>
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">
                {ROUTING_MODE_DESCRIPTIONS[mode]}
              </p>
            </button>
          )
        })}
      </div>

      {/* Cost Opt extra settings */}
      {selectedMode === 'cost_opt' && (
        <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-sm font-medium text-amber-800 mb-3">Cost Optimization Settings</p>
          <div>
            <label className="flex items-center justify-between text-sm text-gray-700 mb-2">
              <span>Quality floor</span>
              <span className="font-mono text-xs bg-white border border-gray-200 px-2 py-0.5 rounded">
                {qualityFloor.toFixed(1)}
              </span>
            </label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.1}
              value={qualityFloor}
              onChange={(e) => setQualityFloor(parseFloat(e.target.value))}
              className="w-full accent-red-500"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>0.0 — cheapest</span>
              <span>1.0 — safest</span>
            </div>
            <p className="text-xs text-amber-700 mt-2">
              Prevents routing complex queries to cheap models. Set higher if accuracy is critical.
            </p>
          </div>
        </div>
      )}

      {/* Round robin note */}
      {selectedMode === 'round_robin' && (
        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-xs text-blue-700">
            Set the <span className="font-semibold">Weight</span> on each model config below to control
            how often it gets selected. Higher weight = more traffic.
          </p>
        </div>
      )}

      {/* Intent note */}
      {selectedMode === 'intent' && (
        <div className="mt-4 p-3 bg-purple-50 border border-purple-200 rounded-lg">
          <p className="text-xs text-purple-700">
            Assign <span className="font-semibold">Intent Tags</span> on each model config below to
            control which query types it handles (e.g., code, math, simple_qa).
          </p>
        </div>
      )}

      {/* JEV settings */}
      {selectedMode === 'jev' && (
        <div className="mt-4 p-4 bg-indigo-50 border border-indigo-200 rounded-lg space-y-4">
          <p className="text-sm font-medium text-indigo-800">JEV Routing Settings</p>

          <div className="space-y-2">
            <label className="flex items-start gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={jevModelRouting}
                onChange={(e) => setJevModelRouting(e.target.checked)}
                className="mt-0.5 accent-red-500"
              />
              <span>
                <span className="font-medium">Model routing</span>
                <span className="block text-xs text-gray-500">
                  Pick a model tier per turn from the mapping below.
                </span>
              </span>
            </label>
            <label className="flex items-start gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={jevToolFiltering}
                onChange={(e) => setJevToolFiltering(e.target.checked)}
                className="mt-0.5 accent-red-500"
              />
              <span>
                <span className="font-medium">Tool filtering</span>
                <span className="block text-xs text-gray-500">
                  Remove built-in tools the query doesn&apos;t need. MCP tools are never filtered.
                </span>
              </span>
            </label>
          </div>

          {jevModelRouting && (
            <div>
              <p className="text-sm text-gray-700 mb-2">Tier → model</p>
              {enabledConfigs.length === 0 ? (
                <p className="text-xs text-amber-700">
                  Add at least one enabled model config below to map tiers.
                </p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {JEV_TIERS.map(({ value, label, hint }) => (
                    <div key={value}>
                      <label className="block text-xs font-medium text-gray-700 mb-1">{label}</label>
                      <select
                        value={jevTierMap[value] ?? ''}
                        onChange={(e) =>
                          setJevTierMap((prev) => ({ ...prev, [value]: e.target.value || undefined }))
                        }
                        className="w-full text-sm border border-gray-300 rounded-lg px-2 py-1.5 bg-white"
                      >
                        <option value="">Default model</option>
                        {enabledConfigs.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name} ({c.model_name})
                          </option>
                        ))}
                      </select>
                      <p className="text-xs text-gray-500 mt-1">{hint}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {jevToolFiltering && (
            <div>
              <label className="block text-sm text-gray-700 mb-1">Tool filtering strictness</label>
              <select
                value={jevThreshold}
                onChange={(e) => setJevThreshold(e.target.value as 'yes' | 'unclear')}
                className="w-full sm:w-72 text-sm border border-gray-300 rounded-lg px-2 py-1.5 bg-white"
              >
                <option value="yes">Strict — keep tools only when clearly needed</option>
                <option value="unclear">Permissive — also keep tools when unsure</option>
              </select>
            </div>
          )}

          {jevInvalid && (
            <p className="text-xs text-red-600">Enable at least one of model routing or tool filtering.</p>
          )}

          <p className="text-xs text-indigo-700">
            Requires a TypeSafe API key under{' '}
            <Link href="/settings/integrations" className="underline font-medium">
              Settings → Integrations → AI Evaluation
            </Link>
            . Without it, routing silently falls back to the built-in intent classifier and no tools are
            filtered. JEV adds one API call before every turn.
          </p>
        </div>
      )}
    </div>
  )
}
