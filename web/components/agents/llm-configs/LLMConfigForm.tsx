'use client'

import { useEffect, useState } from 'react'
import {
  AlertCircle, BarChart3, Bot, Brain, Check, ChevronDown, ChevronUp, Cloud, ExternalLink, Hash, Info, Link, Monitor,
  Mountain, RefreshCw, Rocket, Search, Server, Shuffle, Smile, Sparkles, Triangle, Waves, Wind, Zap,
  type LucideIcon,
} from 'lucide-react'
import toast from 'react-hot-toast'
import {
  AgentLLMConfig,
  AgentLLMConfigCreate,
  AgentLLMConfigUpdate,
  RoutingRules,
  INTENT_OPTIONS,
} from '@/types/agent-llm-config'
import { getLLMProviders, getProviderModels, ProviderPreset, ModelPreset } from '@/lib/api/llm-providers'

// Models that only support temperature=1 (OpenAI reasoning/o-series and gpt-5)
function isReasoningModel(modelName: string): boolean {
  const base = modelName.split('/').pop()?.toLowerCase() ?? ''
  return /^(o1|o3|o4|gpt-5)/.test(base)
}

const PROVIDER_ICONS: Record<string, LucideIcon> = {
  openai: Bot,
  anthropic: Brain,
  google: Sparkles,
  gemini: Sparkles,
  deepseek: Waves,
  ollama: Server,
  huggingface: Smile,
  together_ai: Link,
  cohere: BarChart3,
  mistral: Wind,
  groq: Zap,
  perplexity: Search,
  litellm: Link,
  openrouter: Shuffle,
  azure_openai: Cloud,
  bedrock: Mountain,
  vertex_ai: Triangle,
  lm_studio: Monitor,
  vllm: Rocket,
  replicate: RefreshCw,
  minimax: Hash,
  default: Bot,
}

interface LLMConfigFormProps {
  config?: AgentLLMConfig
  onSubmit: (data: AgentLLMConfigCreate | AgentLLMConfigUpdate) => Promise<void>
  onCancel: () => void
  isSubmitting?: boolean
}

export default function LLMConfigForm({
  config,
  onSubmit,
  onCancel,
  isSubmitting = false,
}: LLMConfigFormProps) {
  const [providers, setProviders] = useState<ProviderPreset[]>([])
  const [models, setModels] = useState<ModelPreset[]>([])
  const [selectedProvider, setSelectedProvider] = useState<ProviderPreset | null>(null)
  const [selectedModel, setSelectedModel] = useState<ModelPreset | null>(null)
  const [loadingProviders, setLoadingProviders] = useState(true)
  const [loadingModels, setLoadingModels] = useState(false)

  const [formData, setFormData] = useState({
    name: config?.name || '',
    provider: config?.provider || '',
    model_name: config?.model_name || '',
    api_key: '',
    api_base: config?.api_base || '',
    temperature: config?.temperature?.toString() || '0.7',
    max_tokens: config?.max_tokens?.toString() || '16384',
    top_p: config?.top_p?.toString() || '1.0',
    enabled: config?.enabled !== undefined ? config.enabled : true,
  })

  const [showApiKey, setShowApiKey] = useState(false)
  const [modelSearch, setModelSearch] = useState('')
  const [showRoutingRules, setShowRoutingRules] = useState(
    !!(config?.routing_rules && Object.keys(config.routing_rules).length > 0)
  )
  const [routingRules, setRoutingRules] = useState<RoutingRules>(config?.routing_rules || {})
  const [routingWeight, setRoutingWeight] = useState<string>(
    config?.routing_weight?.toString() || '1.0'
  )

  useEffect(() => {
    let cancelled = false

    const loadProviders = async () => {
      try {
        setLoadingProviders(true)
        const data = await getLLMProviders()
        if (!cancelled) {
          setProviders(data)
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to load providers:', error)
          toast.error('Failed to load LLM providers')
        }
      } finally {
        if (!cancelled) {
          setLoadingProviders(false)
        }
      }
    }

    loadProviders()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const provider = providers.find((p: ProviderPreset) => p.provider_id === formData.provider) || null
    setSelectedProvider(provider)
  }, [providers, formData.provider])

  useEffect(() => {
    if (!formData.provider) {
      setModels([])
      setSelectedModel(null)
      setLoadingModels(false)
      return
    }

    let cancelled = false

    const loadModels = async () => {
      try {
        setLoadingModels(true)
        const providerModels = await getProviderModels(formData.provider)
        if (!cancelled) {
          setModels(providerModels)
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to load models:', error)
          toast.error('Failed to load models for provider')
        }
      } finally {
        if (!cancelled) {
          setLoadingModels(false)
        }
      }
    }

    loadModels()
    return () => {
      cancelled = true
    }
  }, [formData.provider])

  useEffect(() => {
    if (!formData.model_name) {
      setSelectedModel(null)
      return
    }

    const model = models.find((item: ModelPreset) => item.model_name === formData.model_name) || null
    setSelectedModel(model)
  }, [models, formData.model_name])

  // Handle provider change
  const handleProviderChange = (providerId: string) => {
    const provider = providers.find((p: ProviderPreset) => p.provider_id === providerId)
    setSelectedProvider(provider || null)
    setFormData(prev => ({
      ...prev,
      provider: providerId,
      model_name: '',
      api_base: provider?.default_api_base || '',
    }))
    setSelectedModel(null)
    setModelSearch('')
    setModels([])
  }

  // Handle model change
  const handleModelChange = (modelName: string) => {
    const model = models.find((m: ModelPreset) => m.model_name === modelName)
    setSelectedModel(model || null)
    setFormData(prev => ({
      ...prev,
      model_name: modelName,
      // Auto-populate max_tokens and temperature from model preset (only if not editing existing config)
      ...(model?.default_max_tokens && !config ? { max_tokens: model.default_max_tokens.toString() } : {}),
      ...(!config && model?.default_temperature !== undefined ? { temperature: model.default_temperature.toString() } : {}),
      // Reasoning models only support temperature=1 (always enforce regardless of editing state)
      ...(isReasoningModel(modelName) ? { temperature: '1' } : {}),
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Validation
    if (!formData.name.trim()) {
      toast.error('Please enter a configuration name')
      return
    }

    if (!formData.model_name) {
      toast.error('Please select a model')
      return
    }

    if (!config && selectedProvider?.requires_api_key && !formData.api_key.trim()) {
      toast.error('Please enter an API key')
      return
    }

    try {
      const data: any = {
        name: formData.name.trim(),
        provider: formData.provider,
        model_name: formData.model_name,
        api_base: formData.api_base.trim() || undefined,
        temperature: isReasoningModel(formData.model_name) ? undefined : (parseFloat(formData.temperature) || undefined),
        max_tokens: parseInt(formData.max_tokens) || undefined,
        top_p: parseFloat(formData.top_p) || undefined,
        enabled: formData.enabled, // Include enabled flag
      }

      // Only include API key if it's provided
      if (formData.api_key.trim()) {
        data.api_key = formData.api_key.trim()
      } else if (!config && !selectedProvider?.requires_api_key) {
        data.api_key = 'not-required'
      }

      // Include routing fields
      if (showRoutingRules && Object.keys(routingRules).length > 0) {
        data.routing_rules = routingRules
      }
      const weight = parseFloat(routingWeight)
      if (!isNaN(weight) && weight !== 1.0) {
        data.routing_weight = weight
      }

      await onSubmit(data)
    } catch (error) {
      console.error('Form submission error:', error)
    }
  }

  if (loadingProviders) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="motion-safe:animate-spin rounded-full h-8 w-8 border-b-2 border-danger mx-auto mb-4"></div>
          <p className="text-sm text-ink-mute">Loading providers…</p>
        </div>
      </div>
    )
  }

  const allFilteredModels = modelSearch.trim()
    ? models.filter(m =>
        m.name.toLowerCase().includes(modelSearch.toLowerCase()) ||
        m.model_name.toLowerCase().includes(modelSearch.toLowerCase())
      )
    : models

  const filteredModels = allFilteredModels.filter(
    (m) => !m.tags?.includes('image_generation') && !m.tags?.includes('video_generation')
  )
  const imageModels = allFilteredModels.filter(m => m.tags?.includes('image_generation'))
  const videoModels = allFilteredModels.filter(m => m.tags?.includes('video_generation'))

  return (
    <form onSubmit={handleSubmit} className="space-y-7">

      {/* ── Config Name ─────────────────────────────────────────── */}
      <div>
        <label htmlFor="name" className="block text-sm font-semibold text-ink-soft mb-1.5">
          Configuration Name <span className="text-leaf">*</span>
        </label>
        <input
          type="text"
          id="name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder="e.g., Primary GPT-4, Backup Claude"
          className="w-full px-4 py-2.5 border border-taupe rounded-xl focus:ring-2 focus:ring-ink focus:border-transparent text-sm"
          disabled={isSubmitting}
        />
      </div>

      {/* ── Provider ─────────────────────────────────────────────── */}
      <div>
        <p className="text-sm font-semibold text-ink-soft mb-3">
          Provider <span className="text-leaf">*</span>
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-56 overflow-y-auto pr-0.5">
          {providers.map((provider: ProviderPreset) => {
            const isActive = formData.provider === provider.provider_id
            return (
              <button
                key={provider.provider_id}
                type="button"
                onClick={() => handleProviderChange(provider.provider_id)}
                disabled={isSubmitting}
                className={`relative flex items-center gap-2.5 px-3 py-2.5 rounded-xl border-2 text-left transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-150 ${
                  isActive
                    ? 'border-ink bg-blush-wash shadow-sm'
                    : 'border-line bg-white hover:border-taupe hover:bg-cream'
                }`}
              >
                {(() => {
                  const ProviderIcon = PROVIDER_ICONS[provider.provider_id] ?? PROVIDER_ICONS.default
                  return <ProviderIcon className="h-5 w-5 shrink-0" aria-hidden="true" />
                })()}
                <div className="min-w-0">
                  <p className={`text-sm font-semibold truncate leading-tight ${isActive ? 'text-leaf' : 'text-ink'}`}>
                    {provider.provider_name}
                  </p>
                  <p className="text-xs text-ash mt-0.5">
                    {provider.model_count ?? provider.models?.length ?? 0} models
                  </p>
                </div>
                {isActive && (
                  <div className="absolute top-1.5 right-1.5 w-4 h-4 bg-ink rounded-full flex items-center justify-center">
                    <Check size={9} className="text-white" />
                  </div>
                )}
              </button>
            )
          })}
        </div>
        {selectedProvider && (
          <div className="mt-3 flex items-start gap-2 px-3 py-2.5 bg-cream border border-line rounded-xl">
            <Info className="w-4 h-4 text-ash shrink-0 mt-0.5" />
            <div className="min-w-0">
              <p className="text-xs text-ink-soft leading-relaxed">{selectedProvider.description}</p>
              {selectedProvider.documentation_url && (
                <a
                  href={selectedProvider.documentation_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-leaf hover:text-leaf font-medium mt-1"
                >
                  Documentation <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Model ─────────────────────────────────────────────────── */}
      {formData.provider && (
        <div>
          <p className="text-sm font-semibold text-ink-soft mb-3">
            Model <span className="text-leaf">*</span>
          </p>

          {loadingModels ? (
            <div className="flex items-center gap-3 py-8 justify-center bg-cream rounded-xl border border-sand">
              <div className="motion-safe:animate-spin rounded-full h-5 w-5 border-b-2 border-ink" />
              <span className="text-sm text-ink-mute">Loading models…</span>
            </div>
          ) : models.length > 0 ? (
            <>
              {models.length > 4 && (
                <div className="mb-3">
                  <input
                    type="text"
                    value={modelSearch}
                    onChange={(e) => setModelSearch(e.target.value)}
                    placeholder="Search models…"
                    className="w-full px-4 py-2.5 border border-line rounded-xl text-sm focus:ring-2 focus:ring-ink focus:border-transparent"
                  />
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-[420px] overflow-y-auto pr-0.5">
                {filteredModels.map((model: ModelPreset, index: number) => {
                  const isSelected = formData.model_name === model.model_name
                  const score = model.quality_score
                  const qualityPct = score !== null ? (score / 10) * 100 : null
                  const qualityBarColor = score !== null
                    ? score >= 9 ? 'bg-leaf' : score >= 8 ? 'bg-honey' : 'bg-taupe'
                    : ''
                  const qualityTextColor = score !== null
                    ? score >= 9 ? 'text-leaf' : score >= 8 ? 'text-warn' : 'text-ink-mute'
                    : ''

                  return (
                    <button
                      key={model.model_name}
                      type="button"
                      onClick={() => handleModelChange(model.model_name)}
                      disabled={isSubmitting}
                      className={`relative flex flex-col rounded-xl border-2 text-left transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-150 overflow-hidden ${
                        isSelected
                          ? 'border-ink shadow-md shadow-red-500/10'
                          : 'border-line bg-white hover:border-taupe hover:shadow-sm'
                      }`}
                    >
                      {/* Accent strip */}
                      <div className={`h-0.5 w-full ${isSelected ? 'bg-ink' : 'bg-transparent'}`} />

                      {/* Card body */}
                      <div className={`flex-1 px-4 pt-3 pb-2.5 ${isSelected ? 'bg-blush-wash' : ''}`}>
                        <div className="flex items-start justify-between gap-2 mb-0.5">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className={`font-bold text-sm leading-tight ${isSelected ? 'text-wine' : 'text-ink'}`}>
                              {model.name}
                            </span>
                            {index === 0 && !modelSearch && (
                              <span className="px-1.5 py-0.5 bg-leaf-wash text-forest text-[10px] font-bold rounded-full">
                                Best
                              </span>
                            )}
                            {model.is_open_source && (
                              <span className="px-1.5 py-0.5 bg-sand-deep text-ink-soft text-[10px] font-bold rounded-full">
                                OSS
                              </span>
                            )}
                          </div>
                          {isSelected && (
                            <div className="shrink-0 w-5 h-5 bg-ink rounded-full flex items-center justify-center">
                              <Check size={11} className="text-white" />
                            </div>
                          )}
                        </div>
                        <p className="text-[11px] text-ash font-mono truncate mb-2">{model.model_name}</p>
                        <p className="text-xs text-ink-mute leading-relaxed line-clamp-2">{model.description}</p>
                      </div>

                      {/* Metrics footer */}
                      <div className={`grid grid-cols-3 divide-x border-t text-left ${
                        isSelected
                          ? 'bg-blush-wash/50 border-blush divide-blush'
                          : 'bg-cream border-sand divide-sand'
                      }`}>
                        <div className="px-3 py-2">
                          <p className="text-[9px] font-bold text-ash mb-1">Quality</p>
                          {score !== null ? (
                            <>
                              <p className={`text-base font-bold tabular-nums leading-none ${qualityTextColor}`}>{score.toFixed(1)}</p>
                              <div className="mt-1 h-1 w-full bg-line rounded-full overflow-hidden">
                                <div className={`h-full rounded-full ${qualityBarColor}`} style={{ width: `${qualityPct}%` }} />
                              </div>
                            </>
                          ) : <p className="text-sm text-ash">—</p>}
                        </div>

                        <div className="px-3 py-2">
                          <p className="text-[9px] font-bold text-ash mb-1.5">Speed</p>
                          {model.speed_tier ? (
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-bold ${
                              model.speed_tier === 'fast'   ? 'bg-leaf-wash text-forest' :
                              model.speed_tier === 'medium' ? 'bg-sand-deep text-gold' :
                                                              'bg-blush-wash text-leaf'
                            }`}>
                              {model.speed_tier === 'fast' && <Zap className="w-2.5 h-2.5" />}
                              {model.speed_tier.charAt(0).toUpperCase() + model.speed_tier.slice(1)}
                            </span>
                          ) : <p className="text-sm text-ash">—</p>}
                        </div>

                        <div className="px-3 py-2">
                          <p className="text-[9px] font-bold text-ash mb-1">Cost /1M</p>
                          {model.cost_input_per_1m === null ? (
                            <p className="text-sm text-ash">—</p>
                          ) : model.cost_input_per_1m === 0 ? (
                            <p className="text-sm font-bold text-leaf">Free</p>
                          ) : (
                            <>
                              <p className="text-sm font-bold text-ink tabular-nums leading-tight">${model.cost_input_per_1m}</p>
                              <p className="text-[10px] text-ash tabular-nums">${model.cost_output_per_1m} out</p>
                            </>
                          )}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>

              {filteredModels.length === 0 && modelSearch && imageModels.length === 0 && videoModels.length === 0 && (
                <p className="text-sm text-ink-mute text-center py-6">No models match "{modelSearch}"</p>
              )}

              {/* Image generation models section */}
              {imageModels.length > 0 && (
                <div className="mt-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="h-px flex-1 bg-sand" />
                    <span className="text-xs font-bold text-ash flex items-center gap-1.5">
                      <span className="inline-block w-2 h-2 rounded-full bg-plum" />
                      Image Generation
                    </span>
                    <div className="h-px flex-1 bg-sand" />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {imageModels.map((model: ModelPreset) => {
                      const isSelected = formData.model_name === model.model_name
                      return (
                        <button
                          key={model.model_name}
                          type="button"
                          onClick={() => handleModelChange(model.model_name)}
                          disabled={isSubmitting}
                          className={`relative flex flex-col rounded-xl border-2 text-left transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-150 overflow-hidden ${
                            isSelected
                              ? 'border-plum shadow-md shadow-violet-500/10'
                              : 'border-line bg-white hover:border-blush hover:shadow-sm'
                          }`}
                        >
                          <div className={`h-0.5 w-full ${isSelected ? 'bg-plum' : 'bg-transparent'}`} />
                          <div className={`px-4 pt-3 pb-3 ${isSelected ? 'bg-blush-wash' : ''}`}>
                            <div className="flex items-start justify-between gap-2 mb-0.5">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className={`font-bold text-sm leading-tight ${isSelected ? 'text-wine' : 'text-ink'}`}>
                                  {model.name}
                                </span>
                                <span className="px-1.5 py-0.5 bg-sand-deep text-ink-soft text-[10px] font-bold rounded-full">
                                  Image
                                </span>
                              </div>
                              {isSelected && (
                                <div className="shrink-0 w-5 h-5 bg-plum rounded-full flex items-center justify-center">
                                  <Check size={11} className="text-white" />
                                </div>
                              )}
                            </div>
                            <p className="text-[11px] text-ash font-mono truncate mb-1">{model.model_name}</p>
                            <p className="text-xs text-ink-mute leading-relaxed line-clamp-2">{model.description}</p>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                  <p className="mt-2 text-[11px] text-ash">
                    Image models are used by the Image Generation tool, not for chat.
                    Enable the tool in the agent&apos;s Tools tab.
                  </p>
                </div>
              )}

              {videoModels.length > 0 && (
                <div className="mt-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="h-px flex-1 bg-sand" />
                    <span className="text-xs font-bold text-ash flex items-center gap-1.5">
                      <span className="inline-block w-2 h-2 rounded-full bg-steel" />
                      Video Generation
                    </span>
                    <div className="h-px flex-1 bg-sand" />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {videoModels.map((model: ModelPreset) => {
                      const isSelected = formData.model_name === model.model_name
                      return (
                        <button
                          key={model.model_name}
                          type="button"
                          onClick={() => handleModelChange(model.model_name)}
                          disabled={isSubmitting}
                          className={`relative flex flex-col rounded-xl border-2 text-left transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-150 overflow-hidden ${
                            isSelected
                              ? 'border-azure shadow-md shadow-sky-500/10'
                              : 'border-line bg-white hover:border-steel hover:shadow-sm'
                          }`}
                        >
                          <div className={`h-0.5 w-full ${isSelected ? 'bg-azure' : 'bg-transparent'}`} />
                          <div className={`px-4 pt-3 pb-3 ${isSelected ? 'bg-sky-wash' : ''}`}>
                            <div className="flex items-start justify-between gap-2 mb-0.5">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className={`font-bold text-sm leading-tight ${isSelected ? 'text-azure' : 'text-ink'}`}>
                                  {model.name}
                                </span>
                                <span className="px-1.5 py-0.5 bg-sky-wash text-azure text-[10px] font-bold rounded-full">
                                  Video
                                </span>
                              </div>
                              {isSelected && (
                                <div className="shrink-0 w-5 h-5 bg-azure rounded-full flex items-center justify-center">
                                  <Check size={11} className="text-white" />
                                </div>
                              )}
                            </div>
                            <p className="text-[11px] text-ash font-mono truncate mb-1">{model.model_name}</p>
                            <p className="text-xs text-ink-mute leading-relaxed line-clamp-2">{model.description}</p>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                  <p className="mt-2 text-[11px] text-ash">
                    Video models are for media generation workflows, not for chat completions.
                  </p>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-ink-mute text-center py-8 bg-cream rounded-xl border border-sand">
              No models available for this provider
            </p>
          )}
        </div>
      )}

      {/* ── API Key ──────────────────────────────────────────────── */}
      {selectedProvider?.requires_api_key && (
        <div>
          <label htmlFor="api_key" className="block text-sm font-semibold text-ink-soft mb-1.5">
            API Key {!config && <span className="text-leaf">*</span>}
          </label>
          <div className="relative">
            <input
              type={showApiKey ? 'text' : 'password'}
              id="api_key"
              value={formData.api_key}
              onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
              placeholder={config ? 'Leave blank to keep existing key' : 'Paste your API key here'}
              className="w-full px-4 py-2.5 pr-20 border border-taupe rounded-xl focus:ring-2 focus:ring-ink focus:border-transparent text-sm font-mono"
              disabled={isSubmitting}
            />
            <button
              type="button"
              onClick={() => setShowApiKey(!showApiKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-ink-mute hover:text-ink-soft px-2 py-1 rounded-md hover:bg-sand transition-colors"
            >
              {showApiKey ? 'Hide' : 'Show'}
            </button>
          </div>
          {selectedProvider.setup_instructions && (
            <p className="flex items-start gap-1.5 text-xs text-ink-mute mt-1.5">
              <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-ash" />
              {selectedProvider.setup_instructions}
            </p>
          )}
          {config && (
            <p className="text-xs text-ash mt-1">Leave blank to keep the existing key.</p>
          )}
        </div>
      )}

      {/* ── API Base URL ─────────────────────────────────────────── */}
      {selectedProvider && (selectedProvider.requires_api_base || selectedProvider.default_api_base) && (
        <div>
          <label htmlFor="api_base" className="block text-sm font-semibold text-ink-soft mb-1.5">
            API Base URL {selectedProvider.requires_api_base && <span className="text-leaf">*</span>}
          </label>
          <input
            type="url"
            id="api_base"
            value={formData.api_base}
            onChange={(e) => setFormData({ ...formData, api_base: e.target.value })}
            placeholder={selectedProvider.default_api_base ?? 'https://api.example.com/v1'}
            className="w-full px-4 py-2.5 border border-taupe rounded-xl focus:ring-2 focus:ring-ink focus:border-transparent text-sm font-mono"
            disabled={isSubmitting}
          />
          <p className="text-xs text-ash mt-1">Custom API endpoint (e.g., for self-hosted models)</p>
        </div>
      )}

      {/* ── Special-provider warning ─────────────────────────────── */}
      {selectedProvider && ['bedrock', 'vertex_ai', 'azure_openai'].includes(selectedProvider.provider_id) && (
        <div className="flex items-start gap-3 p-4 bg-sand-deep border border-honey rounded-xl">
          <AlertCircle className="w-5 h-5 text-warn shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-gold">Additional setup required</p>
            <p className="text-sm text-gold mt-0.5">{selectedProvider.setup_instructions}</p>
            <p className="text-xs text-warn mt-1">
              You may need to add credentials in additional_params via the API.
            </p>
          </div>
        </div>
      )}

      {/* ── Advanced Settings ────────────────────────────────────── */}
      <div className="border-t border-sand pt-6">
        <p className="text-sm font-semibold text-ink-soft mb-4">Advanced Settings</p>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label htmlFor="temperature" className="block text-xs font-semibold text-ink-mute mb-1.5">
              Temperature
            </label>
            <input
              type="number"
              id="temperature"
              value={formData.temperature}
              onChange={(e) => setFormData({ ...formData, temperature: e.target.value })}
              min="0" max="2" step="0.1"
              className={`w-full px-3 py-2 border rounded-lg text-sm ${
                isReasoningModel(formData.model_name)
                  ? 'border-line bg-cream text-ash cursor-not-allowed'
                  : 'border-line focus:ring-2 focus:ring-ink focus:border-transparent'
              }`}
              disabled={isSubmitting || isReasoningModel(formData.model_name)}
            />
            {isReasoningModel(formData.model_name) ? (
              <p className="text-[11px] text-warn mt-1">Fixed at 1, not supported by this model</p>
            ) : (
              <p className="text-[11px] text-ash mt-1">0 – 2</p>
            )}
          </div>
          <div>
            <label htmlFor="max_tokens" className="block text-xs font-semibold text-ink-mute mb-1.5">
              Max Tokens
            </label>
            <input
              type="number"
              id="max_tokens"
              value={formData.max_tokens}
              onChange={(e) => setFormData({ ...formData, max_tokens: e.target.value })}
              min="1"
              max={selectedModel?.max_output_tokens ?? 200000}
              step="1"
              className="w-full px-3 py-2 border border-line rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent text-sm"
              disabled={isSubmitting}
            />
            <p className="text-[11px] text-ash mt-1">
              {selectedModel?.max_output_tokens
                ? `Max ${selectedModel.max_output_tokens.toLocaleString()}`
                : selectedModel?.default_max_tokens
                  ? `Rec. ${selectedModel.default_max_tokens.toLocaleString()}`
                  : 'Max output'}
            </p>
          </div>
          <div>
            <label htmlFor="top_p" className="block text-xs font-semibold text-ink-mute mb-1.5">
              Top P
            </label>
            <input
              type="number"
              id="top_p"
              value={formData.top_p}
              onChange={(e) => setFormData({ ...formData, top_p: e.target.value })}
              min="0" max="1" step="0.1"
              className="w-full px-3 py-2 border border-line rounded-lg focus:ring-2 focus:ring-ink focus:border-transparent text-sm"
              disabled={isSubmitting}
            />
            <p className="text-[11px] text-ash mt-1">0 – 1</p>
          </div>
        </div>
      </div>

      {/* ── Enable toggle ────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 bg-cream rounded-xl border border-line">
        <div>
          <p className="text-sm font-semibold text-ink">Enable this configuration</p>
          <p className="text-xs text-ink-mute mt-0.5">Disabled configs won't be used by the agent</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={formData.enabled}
          onClick={() => setFormData({ ...formData, enabled: !formData.enabled })}
          disabled={isSubmitting}
          className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ink focus:ring-offset-2 ${
            formData.enabled ? 'bg-ink' : 'bg-line'
          }`}
        >
          <span className={`inline-block h-5 w-5 rounded-full bg-white shadow transform transition-transform motion-reduce:transition-none duration-200 ${
            formData.enabled ? 'translate-x-5' : 'translate-x-0'
          }`} />
        </button>
      </div>

      {/* ── Routing Rules ────────────────────────────────────────── */}
      <div className="border-t border-sand pt-5">
        <button
          type="button"
          onClick={() => setShowRoutingRules(!showRoutingRules)}
          className="flex items-center gap-2 text-sm font-semibold text-ink-soft hover:text-ink"
        >
          {showRoutingRules ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          Routing Rules
          <span className="text-xs font-normal text-ash">(optional, controls when this model is selected)</span>
        </button>

        {showRoutingRules && (
          <div className="mt-4 space-y-4">
            {/* Intent tags */}
            <div>
              <label className="block text-xs font-semibold text-ink-mute mb-2">
                Handle These Intents
              </label>
              <div className="flex flex-wrap gap-2">
                {INTENT_OPTIONS.map(({ value, label }) => {
                  const selected = (routingRules.intents || []).includes(value)
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => {
                        const current = routingRules.intents || []
                        setRoutingRules({
                          ...routingRules,
                          intents: selected
                            ? current.filter((i) => i !== value)
                            : [...current, value],
                        })
                      }}
                      className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                        selected
                          ? 'bg-blush-wash border-hotpink text-leaf font-medium'
                          : 'bg-cream border-line text-ink-soft hover:border-taupe'
                      }`}
                    >
                      {label}
                    </button>
                  )
                })}
              </div>
              <p className="text-[11px] text-ash mt-1.5">
                Leave empty to match any intent.
              </p>
            </div>

            {/* Complexity range */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-ink-mute mb-1.5">
                  Min Complexity
                </label>
                <input
                  type="number"
                  value={routingRules.min_complexity ?? ''}
                  onChange={(e) =>
                    setRoutingRules({
                      ...routingRules,
                      min_complexity: e.target.value ? parseFloat(e.target.value) : undefined,
                    })
                  }
                  placeholder="0.0"
                  min={0}
                  max={1}
                  step={0.1}
                  className="w-full px-3 py-2 border border-line rounded-lg text-sm focus:ring-2 focus:ring-ink focus:border-transparent"
                />
                <p className="text-[11px] text-ash mt-1">0.0 = trivial query</p>
              </div>
              <div>
                <label className="block text-xs font-semibold text-ink-mute mb-1.5">
                  Max Complexity
                </label>
                <input
                  type="number"
                  value={routingRules.max_complexity ?? ''}
                  onChange={(e) =>
                    setRoutingRules({
                      ...routingRules,
                      max_complexity: e.target.value ? parseFloat(e.target.value) : undefined,
                    })
                  }
                  placeholder="1.0"
                  min={0}
                  max={1}
                  step={0.1}
                  className="w-full px-3 py-2 border border-line rounded-lg text-sm focus:ring-2 focus:ring-ink focus:border-transparent"
                />
                <p className="text-[11px] text-ash mt-1">1.0 = very complex</p>
              </div>
            </div>

            {/* Cost and priority */}
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-ink-mute mb-1.5">
                  Cost / 1k Input (USD)
                </label>
                <input
                  type="number"
                  value={routingRules.cost_per_1k_input ?? ''}
                  onChange={(e) =>
                    setRoutingRules({
                      ...routingRules,
                      cost_per_1k_input: e.target.value ? parseFloat(e.target.value) : undefined,
                    })
                  }
                  placeholder="0.003"
                  min={0}
                  step={0.0001}
                  className="w-full px-3 py-2 border border-line rounded-lg text-sm focus:ring-2 focus:ring-ink focus:border-transparent"
                />
                <p className="text-[11px] text-ash mt-1">Used by cost_opt mode</p>
              </div>
              <div>
                <label className="block text-xs font-semibold text-ink-mute mb-1.5">
                  Priority
                </label>
                <input
                  type="number"
                  value={routingRules.priority ?? ''}
                  onChange={(e) =>
                    setRoutingRules({
                      ...routingRules,
                      priority: e.target.value ? parseInt(e.target.value) : undefined,
                    })
                  }
                  placeholder="1"
                  min={1}
                  step={1}
                  className="w-full px-3 py-2 border border-line rounded-lg text-sm focus:ring-2 focus:ring-ink focus:border-transparent"
                />
                <p className="text-[11px] text-ash mt-1">Lower = preferred</p>
              </div>
              <div>
                <label className="block text-xs font-semibold text-ink-mute mb-1.5">
                  Weight (round robin)
                </label>
                <input
                  type="number"
                  value={routingWeight}
                  onChange={(e) => setRoutingWeight(e.target.value)}
                  placeholder="1.0"
                  min={0}
                  max={1}
                  step={0.1}
                  className="w-full px-3 py-2 border border-line rounded-lg text-sm focus:ring-2 focus:ring-ink focus:border-transparent"
                />
                <p className="text-[11px] text-ash mt-1">0.0 – 1.0</p>
              </div>
            </div>

            {/* Fallback only toggle */}
            <div className="flex items-center justify-between px-4 py-3 bg-cream rounded-xl border border-line">
              <div>
                <p className="text-sm font-medium text-ink">Fallback only</p>
                <p className="text-xs text-ink-mute mt-0.5">
                  Only use this model when all other configs fail or circuit breaks
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={routingRules.is_fallback ?? false}
                onClick={() =>
                  setRoutingRules({ ...routingRules, is_fallback: !(routingRules.is_fallback ?? false) })
                }
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ink focus:ring-offset-2 ${
                  routingRules.is_fallback ? 'bg-ink' : 'bg-line'
                }`}
              >
                <span
                  className={`inline-block h-5 w-5 rounded-full bg-white shadow transform transition-transform motion-reduce:transition-none duration-200 ${
                    routingRules.is_fallback ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Actions ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-end gap-3 pt-2 border-t border-sand">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="px-5 py-2.5 border border-line text-ink-soft rounded-xl hover:bg-cream transition-colors disabled:opacity-50 text-sm font-medium"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-6 py-2.5 bg-ink hover:bg-danger text-white rounded-xl transition-colors shadow-sm disabled:opacity-50 text-sm font-semibold"
        >
          {isSubmitting ? 'Saving…' : config ? 'Update Configuration' : 'Create Configuration'}
        </button>
      </div>

    </form>
  )
}
