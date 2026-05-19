'use client'

import { useState, useEffect } from 'react'
import { ExternalLink, Info, AlertCircle, Check, Zap, ChevronDown, ChevronUp } from 'lucide-react'
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

const PROVIDER_ICONS: Record<string, string> = {
  openai: '🤖', anthropic: '🧠', google: '🔮', gemini: '🔮',
  ollama: '🦙', huggingface: '🤗', together_ai: '🔗', cohere: '📊',
  mistral: '🌪️', groq: '⚡', perplexity: '🔍', litellm: '🔗',
  openrouter: '🛣️', azure_openai: '☁️', bedrock: '🪨', vertex_ai: '🔺',
  lm_studio: '🖥️', vllm: '🚀', replicate: '♻️', minimax: '🔢',
  default: '🤖',
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

  // Load providers on mount
  useEffect(() => {
    const loadProviders = async () => {
      try {
        setLoadingProviders(true)
        const data = await getLLMProviders()
        setProviders(data)
        
        // If editing, find the provider and load its models
        if (config?.provider) {
          const provider = data.find((p: ProviderPreset) => p.provider_id === config.provider)
          if (provider) {
            setSelectedProvider(provider)
            await loadModelsForProvider(config.provider)
          }
        }
      } catch (error) {
        console.error('Failed to load providers:', error)
        toast.error('Failed to load LLM providers')
      } finally {
        setLoadingProviders(false)
      }
    }

    loadProviders()
  }, [config])

  // Load models when provider changes
  const loadModelsForProvider = async (providerId: string) => {
    if (!providerId) return

    try {
      setLoadingModels(true)
      const providerModels = await getProviderModels(providerId)
      setModels(providerModels)
      
      // If editing and model exists, select it
      if (config?.model_name) {
        const model = providerModels.find((m: ModelPreset) => m.model_name === config.model_name)
        if (model) {
          setSelectedModel(model)
        }
      }
    } catch (error) {
      console.error('Failed to load models:', error)
      toast.error('Failed to load models for provider')
    } finally {
      setLoadingModels(false)
    }
  }

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

    if (providerId) {
      loadModelsForProvider(providerId)
    } else {
      setModels([])
    }
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
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-600 mx-auto mb-4"></div>
          <p className="text-sm text-gray-500">Loading providers...</p>
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
        <label htmlFor="name" className="block text-sm font-semibold text-gray-700 mb-1.5">
          Configuration Name <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          id="name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder="e.g., Primary GPT-4, Backup Claude"
          className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 focus:border-transparent text-sm"
          disabled={isSubmitting}
        />
      </div>

      {/* ── Provider ─────────────────────────────────────────────── */}
      <div>
        <p className="text-sm font-semibold text-gray-700 mb-3">
          Provider <span className="text-red-500">*</span>
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
                className={`relative flex items-center gap-2.5 px-3 py-2.5 rounded-xl border-2 text-left transition-all duration-150 ${
                  isActive
                    ? 'border-red-500 bg-red-50 shadow-sm'
                    : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                <span className="text-xl shrink-0 leading-none">
                  {PROVIDER_ICONS[provider.provider_id] ?? PROVIDER_ICONS.default}
                </span>
                <div className="min-w-0">
                  <p className={`text-sm font-semibold truncate leading-tight ${isActive ? 'text-red-700' : 'text-gray-800'}`}>
                    {provider.provider_name}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {provider.model_count ?? provider.models?.length ?? 0} models
                  </p>
                </div>
                {isActive && (
                  <div className="absolute top-1.5 right-1.5 w-4 h-4 bg-red-500 rounded-full flex items-center justify-center">
                    <Check size={9} className="text-white" />
                  </div>
                )}
              </button>
            )
          })}
        </div>
        {selectedProvider && (
          <div className="mt-3 flex items-start gap-2 px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl">
            <Info className="w-4 h-4 text-gray-400 shrink-0 mt-0.5" />
            <div className="min-w-0">
              <p className="text-xs text-gray-600 leading-relaxed">{selectedProvider.description}</p>
              {selectedProvider.documentation_url && (
                <a
                  href={selectedProvider.documentation_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-red-600 hover:text-red-700 font-medium mt-1"
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
          <p className="text-sm font-semibold text-gray-700 mb-3">
            Model <span className="text-red-500">*</span>
          </p>

          {loadingModels ? (
            <div className="flex items-center gap-3 py-8 justify-center bg-gray-50 rounded-xl border border-gray-100">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-red-500" />
              <span className="text-sm text-gray-500">Loading models…</span>
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
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  />
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-[420px] overflow-y-auto pr-0.5">
                {filteredModels.map((model: ModelPreset, index: number) => {
                  const isSelected = formData.model_name === model.model_name
                  const score = model.quality_score
                  const qualityPct = score !== null ? (score / 10) * 100 : null
                  const qualityBarColor = score !== null
                    ? score >= 9 ? 'bg-green-500' : score >= 8 ? 'bg-amber-400' : 'bg-gray-300'
                    : ''
                  const qualityTextColor = score !== null
                    ? score >= 9 ? 'text-green-600' : score >= 8 ? 'text-amber-600' : 'text-gray-500'
                    : ''

                  return (
                    <button
                      key={model.model_name}
                      type="button"
                      onClick={() => handleModelChange(model.model_name)}
                      disabled={isSubmitting}
                      className={`relative flex flex-col rounded-xl border-2 text-left transition-all duration-150 overflow-hidden ${
                        isSelected
                          ? 'border-red-500 shadow-md shadow-red-500/10'
                          : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
                      }`}
                    >
                      {/* Accent strip */}
                      <div className={`h-0.5 w-full ${isSelected ? 'bg-red-500' : 'bg-transparent'}`} />

                      {/* Card body */}
                      <div className={`flex-1 px-4 pt-3 pb-2.5 ${isSelected ? 'bg-red-50' : ''}`}>
                        <div className="flex items-start justify-between gap-2 mb-0.5">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className={`font-bold text-sm leading-tight ${isSelected ? 'text-red-800' : 'text-gray-900'}`}>
                              {model.name}
                            </span>
                            {index === 0 && !modelSearch && (
                              <span className="px-1.5 py-0.5 bg-green-100 text-green-700 text-[10px] font-bold rounded-full">
                                Best
                              </span>
                            )}
                            {model.is_open_source && (
                              <span className="px-1.5 py-0.5 bg-violet-100 text-violet-700 text-[10px] font-bold rounded-full">
                                OSS
                              </span>
                            )}
                          </div>
                          {isSelected && (
                            <div className="shrink-0 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center">
                              <Check size={11} className="text-white" />
                            </div>
                          )}
                        </div>
                        <p className="text-[11px] text-gray-400 font-mono truncate mb-2">{model.model_name}</p>
                        <p className="text-xs text-gray-500 leading-relaxed line-clamp-2">{model.description}</p>
                      </div>

                      {/* Metrics footer */}
                      <div className={`grid grid-cols-3 divide-x border-t text-left ${
                        isSelected
                          ? 'bg-red-100/50 border-red-200 divide-red-200'
                          : 'bg-gray-50 border-gray-100 divide-gray-100'
                      }`}>
                        <div className="px-3 py-2">
                          <p className="text-[9px] font-bold uppercase tracking-widest text-gray-400 mb-1">Quality</p>
                          {score !== null ? (
                            <>
                              <p className={`text-base font-bold tabular-nums leading-none ${qualityTextColor}`}>{score.toFixed(1)}</p>
                              <div className="mt-1 h-1 w-full bg-gray-200 rounded-full overflow-hidden">
                                <div className={`h-full rounded-full ${qualityBarColor}`} style={{ width: `${qualityPct}%` }} />
                              </div>
                            </>
                          ) : <p className="text-sm text-gray-400">—</p>}
                        </div>

                        <div className="px-3 py-2">
                          <p className="text-[9px] font-bold uppercase tracking-widest text-gray-400 mb-1.5">Speed</p>
                          {model.speed_tier ? (
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-bold ${
                              model.speed_tier === 'fast'   ? 'bg-green-100 text-green-700' :
                              model.speed_tier === 'medium' ? 'bg-amber-100 text-amber-700' :
                                                              'bg-red-100 text-red-700'
                            }`}>
                              {model.speed_tier === 'fast' && <Zap className="w-2.5 h-2.5" />}
                              {model.speed_tier.charAt(0).toUpperCase() + model.speed_tier.slice(1)}
                            </span>
                          ) : <p className="text-sm text-gray-400">—</p>}
                        </div>

                        <div className="px-3 py-2">
                          <p className="text-[9px] font-bold uppercase tracking-widest text-gray-400 mb-1">Cost /1M</p>
                          {model.cost_input_per_1m === null ? (
                            <p className="text-sm text-gray-400">—</p>
                          ) : model.cost_input_per_1m === 0 ? (
                            <p className="text-sm font-bold text-green-600">Free</p>
                          ) : (
                            <>
                              <p className="text-sm font-bold text-gray-800 tabular-nums leading-tight">${model.cost_input_per_1m}</p>
                              <p className="text-[10px] text-gray-400 tabular-nums">${model.cost_output_per_1m} out</p>
                            </>
                          )}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>

              {filteredModels.length === 0 && modelSearch && imageModels.length === 0 && videoModels.length === 0 && (
                <p className="text-sm text-gray-500 text-center py-6">No models match "{modelSearch}"</p>
              )}

              {/* Image generation models section */}
              {imageModels.length > 0 && (
                <div className="mt-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="h-px flex-1 bg-gray-100" />
                    <span className="text-xs font-bold uppercase tracking-widest text-gray-400 flex items-center gap-1.5">
                      <span className="inline-block w-2 h-2 rounded-full bg-violet-400" />
                      Image Generation
                    </span>
                    <div className="h-px flex-1 bg-gray-100" />
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
                          className={`relative flex flex-col rounded-xl border-2 text-left transition-all duration-150 overflow-hidden ${
                            isSelected
                              ? 'border-violet-500 shadow-md shadow-violet-500/10'
                              : 'border-gray-200 bg-white hover:border-violet-300 hover:shadow-sm'
                          }`}
                        >
                          <div className={`h-0.5 w-full ${isSelected ? 'bg-violet-500' : 'bg-transparent'}`} />
                          <div className={`px-4 pt-3 pb-3 ${isSelected ? 'bg-violet-50' : ''}`}>
                            <div className="flex items-start justify-between gap-2 mb-0.5">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className={`font-bold text-sm leading-tight ${isSelected ? 'text-violet-800' : 'text-gray-900'}`}>
                                  {model.name}
                                </span>
                                <span className="px-1.5 py-0.5 bg-violet-100 text-violet-700 text-[10px] font-bold rounded-full">
                                  Image
                                </span>
                              </div>
                              {isSelected && (
                                <div className="shrink-0 w-5 h-5 bg-violet-500 rounded-full flex items-center justify-center">
                                  <Check size={11} className="text-white" />
                                </div>
                              )}
                            </div>
                            <p className="text-[11px] text-gray-400 font-mono truncate mb-1">{model.model_name}</p>
                            <p className="text-xs text-gray-500 leading-relaxed line-clamp-2">{model.description}</p>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                  <p className="mt-2 text-[11px] text-gray-400">
                    Image models are used by the Image Generation tool — not for chat.
                    Enable the tool in the agent&apos;s Tools tab.
                  </p>
                </div>
              )}

              {videoModels.length > 0 && (
                <div className="mt-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="h-px flex-1 bg-gray-100" />
                    <span className="text-xs font-bold uppercase tracking-widest text-gray-400 flex items-center gap-1.5">
                      <span className="inline-block w-2 h-2 rounded-full bg-sky-400" />
                      Video Generation
                    </span>
                    <div className="h-px flex-1 bg-gray-100" />
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
                          className={`relative flex flex-col rounded-xl border-2 text-left transition-all duration-150 overflow-hidden ${
                            isSelected
                              ? 'border-sky-500 shadow-md shadow-sky-500/10'
                              : 'border-gray-200 bg-white hover:border-sky-300 hover:shadow-sm'
                          }`}
                        >
                          <div className={`h-0.5 w-full ${isSelected ? 'bg-sky-500' : 'bg-transparent'}`} />
                          <div className={`px-4 pt-3 pb-3 ${isSelected ? 'bg-sky-50' : ''}`}>
                            <div className="flex items-start justify-between gap-2 mb-0.5">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className={`font-bold text-sm leading-tight ${isSelected ? 'text-sky-800' : 'text-gray-900'}`}>
                                  {model.name}
                                </span>
                                <span className="px-1.5 py-0.5 bg-sky-100 text-sky-700 text-[10px] font-bold rounded-full">
                                  Video
                                </span>
                              </div>
                              {isSelected && (
                                <div className="shrink-0 w-5 h-5 bg-sky-500 rounded-full flex items-center justify-center">
                                  <Check size={11} className="text-white" />
                                </div>
                              )}
                            </div>
                            <p className="text-[11px] text-gray-400 font-mono truncate mb-1">{model.model_name}</p>
                            <p className="text-xs text-gray-500 leading-relaxed line-clamp-2">{model.description}</p>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                  <p className="mt-2 text-[11px] text-gray-400">
                    Video models are for media generation workflows — not for chat completions.
                  </p>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-gray-500 text-center py-8 bg-gray-50 rounded-xl border border-gray-100">
              No models available for this provider
            </p>
          )}
        </div>
      )}

      {/* ── API Key ──────────────────────────────────────────────── */}
      {selectedProvider?.requires_api_key && (
        <div>
          <label htmlFor="api_key" className="block text-sm font-semibold text-gray-700 mb-1.5">
            API Key {!config && <span className="text-red-500">*</span>}
          </label>
          <div className="relative">
            <input
              type={showApiKey ? 'text' : 'password'}
              id="api_key"
              value={formData.api_key}
              onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
              placeholder={config ? 'Leave blank to keep existing key' : 'Paste your API key here'}
              className="w-full px-4 py-2.5 pr-20 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 focus:border-transparent text-sm font-mono"
              disabled={isSubmitting}
            />
            <button
              type="button"
              onClick={() => setShowApiKey(!showApiKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-gray-500 hover:text-gray-700 px-2 py-1 rounded-md hover:bg-gray-100 transition-colors"
            >
              {showApiKey ? 'Hide' : 'Show'}
            </button>
          </div>
          {selectedProvider.setup_instructions && (
            <p className="flex items-start gap-1.5 text-xs text-gray-500 mt-1.5">
              <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-gray-400" />
              {selectedProvider.setup_instructions}
            </p>
          )}
          {config && (
            <p className="text-xs text-gray-400 mt-1">Leave blank to keep the existing key.</p>
          )}
        </div>
      )}

      {/* ── API Base URL ─────────────────────────────────────────── */}
      {selectedProvider && (selectedProvider.requires_api_base || selectedProvider.default_api_base) && (
        <div>
          <label htmlFor="api_base" className="block text-sm font-semibold text-gray-700 mb-1.5">
            API Base URL {selectedProvider.requires_api_base && <span className="text-red-500">*</span>}
          </label>
          <input
            type="url"
            id="api_base"
            value={formData.api_base}
            onChange={(e) => setFormData({ ...formData, api_base: e.target.value })}
            placeholder={selectedProvider.default_api_base ?? 'https://api.example.com/v1'}
            className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 focus:border-transparent text-sm font-mono"
            disabled={isSubmitting}
          />
          <p className="text-xs text-gray-400 mt-1">Custom API endpoint (e.g., for self-hosted models)</p>
        </div>
      )}

      {/* ── Special-provider warning ─────────────────────────────── */}
      {selectedProvider && ['bedrock', 'vertex_ai', 'azure_openai'].includes(selectedProvider.provider_id) && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <AlertCircle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-amber-900">Additional setup required</p>
            <p className="text-sm text-amber-800 mt-0.5">{selectedProvider.setup_instructions}</p>
            <p className="text-xs text-amber-600 mt-1">
              You may need to add credentials in additional_params via the API.
            </p>
          </div>
        </div>
      )}

      {/* ── Advanced Settings ────────────────────────────────────── */}
      <div className="border-t border-gray-100 pt-6">
        <p className="text-sm font-semibold text-gray-700 mb-4">Advanced Settings</p>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label htmlFor="temperature" className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
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
                  ? 'border-gray-200 bg-gray-50 text-gray-400 cursor-not-allowed'
                  : 'border-gray-200 focus:ring-2 focus:ring-red-500 focus:border-transparent'
              }`}
              disabled={isSubmitting || isReasoningModel(formData.model_name)}
            />
            {isReasoningModel(formData.model_name) ? (
              <p className="text-[11px] text-amber-500 mt-1">Fixed at 1 — not supported by this model</p>
            ) : (
              <p className="text-[11px] text-gray-400 mt-1">0 – 2</p>
            )}
          </div>
          <div>
            <label htmlFor="max_tokens" className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
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
              className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent text-sm"
              disabled={isSubmitting}
            />
            <p className="text-[11px] text-gray-400 mt-1">
              {selectedModel?.max_output_tokens
                ? `Max ${selectedModel.max_output_tokens.toLocaleString()}`
                : selectedModel?.default_max_tokens
                  ? `Rec. ${selectedModel.default_max_tokens.toLocaleString()}`
                  : 'Max output'}
            </p>
          </div>
          <div>
            <label htmlFor="top_p" className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
              Top P
            </label>
            <input
              type="number"
              id="top_p"
              value={formData.top_p}
              onChange={(e) => setFormData({ ...formData, top_p: e.target.value })}
              min="0" max="1" step="0.1"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent text-sm"
              disabled={isSubmitting}
            />
            <p className="text-[11px] text-gray-400 mt-1">0 – 1</p>
          </div>
        </div>
      </div>

      {/* ── Enable toggle ────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 rounded-xl border border-gray-200">
        <div>
          <p className="text-sm font-semibold text-gray-800">Enable this configuration</p>
          <p className="text-xs text-gray-500 mt-0.5">Disabled configs won't be used by the agent</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={formData.enabled}
          onClick={() => setFormData({ ...formData, enabled: !formData.enabled })}
          disabled={isSubmitting}
          className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 ${
            formData.enabled ? 'bg-red-500' : 'bg-gray-200'
          }`}
        >
          <span className={`inline-block h-5 w-5 rounded-full bg-white shadow transform transition-transform duration-200 ${
            formData.enabled ? 'translate-x-5' : 'translate-x-0'
          }`} />
        </button>
      </div>

      {/* ── Routing Rules ────────────────────────────────────────── */}
      <div className="border-t border-gray-100 pt-5">
        <button
          type="button"
          onClick={() => setShowRoutingRules(!showRoutingRules)}
          className="flex items-center gap-2 text-sm font-semibold text-gray-700 hover:text-gray-900"
        >
          {showRoutingRules ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          Routing Rules
          <span className="text-xs font-normal text-gray-400">(optional — controls when this model is selected)</span>
        </button>

        {showRoutingRules && (
          <div className="mt-4 space-y-4">
            {/* Intent tags */}
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
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
                          ? 'bg-red-100 border-red-400 text-red-700 font-medium'
                          : 'bg-gray-50 border-gray-200 text-gray-600 hover:border-gray-300'
                      }`}
                    >
                      {label}
                    </button>
                  )
                })}
              </div>
              <p className="text-[11px] text-gray-400 mt-1.5">
                Leave empty to match any intent.
              </p>
            </div>

            {/* Complexity range */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
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
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent"
                />
                <p className="text-[11px] text-gray-400 mt-1">0.0 = trivial query</p>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
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
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent"
                />
                <p className="text-[11px] text-gray-400 mt-1">1.0 = very complex</p>
              </div>
            </div>

            {/* Cost and priority */}
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
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
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent"
                />
                <p className="text-[11px] text-gray-400 mt-1">Used by cost_opt mode</p>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
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
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent"
                />
                <p className="text-[11px] text-gray-400 mt-1">Lower = preferred</p>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
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
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent"
                />
                <p className="text-[11px] text-gray-400 mt-1">0.0 – 1.0</p>
              </div>
            </div>

            {/* Fallback only toggle */}
            <div className="flex items-center justify-between px-4 py-3 bg-gray-50 rounded-xl border border-gray-200">
              <div>
                <p className="text-sm font-medium text-gray-800">Fallback only</p>
                <p className="text-xs text-gray-500 mt-0.5">
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
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 ${
                  routingRules.is_fallback ? 'bg-red-500' : 'bg-gray-200'
                }`}
              >
                <span
                  className={`inline-block h-5 w-5 rounded-full bg-white shadow transform transition-transform duration-200 ${
                    routingRules.is_fallback ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Actions ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-end gap-3 pt-2 border-t border-gray-100">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="px-5 py-2.5 border border-gray-200 text-gray-600 rounded-xl hover:bg-gray-50 transition-colors disabled:opacity-50 text-sm font-medium"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-6 py-2.5 bg-red-500 hover:bg-red-600 text-white rounded-xl transition-colors shadow-sm disabled:opacity-50 text-sm font-semibold"
        >
          {isSubmitting ? 'Saving…' : config ? 'Update Configuration' : 'Create Configuration'}
        </button>
      </div>

    </form>
  )
}
