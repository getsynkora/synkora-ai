'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Lightbulb,
  User,
  Bot,
  Cpu,
  Zap,
  FileText,
  Smile,
  Briefcase,
  GraduationCap,
  Settings2,
  Sparkles,
  Save,
  Info,
  BarChart3,
  Brain,
  Cloud,
  Diamond,
  Dna,
  Handshake,
  Hexagon,
  Link,
  Mountain,
  Orbit,
  PartyPopper,
  RefreshCw,
  Search,
  Server,
  Shuffle,
  Waves,
  Wind,
  type LucideIcon
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import { AvatarUpload } from '@/components/profile/AvatarUpload'
import CapabilitySelector from '@/components/agents/CapabilitySelector'
import TemplateSelector from '@/components/agents/TemplateSelector'
import { AgentTemplate } from '@/lib/data/agent-templates'
import { getLLMProviders, getProviderModels, ProviderPreset, ModelPreset } from '@/lib/api/llm-providers'

// Steps configuration
const STEPS = [
  { id: 1, name: 'Basics', description: 'Name & Description' },
  { id: 2, name: 'AI Model', description: 'LLM Configuration' },
  { id: 3, name: 'Personality', description: 'Tone & Behavior' },
  { id: 4, name: 'Review', description: 'Confirm & Create' },
]

// Provider icons mapping
const PROVIDER_ICONS: Record<string, LucideIcon> = {
  openai: Bot,
  anthropic: Brain,
  google: Sparkles,
  gemini: Sparkles,
  deepseek: Waves,
  groq: Zap,
  openrouter: Shuffle,
  minimax: Diamond,
  azure_openai: Cloud,
  bedrock: Mountain,
  vertex_ai: Hexagon,
  ollama: Server,
  together_ai: Handshake,
  mistral: Wind,
  cohere: Orbit,
  fireworks: PartyPopper,
  deepinfra: Dna,
  anyscale: BarChart3,
  litellm: Link,
  perplexity: Search,
  replicate: RefreshCw,
  huggingface: Smile,
  default: Bot,
}

// Personality presets
const PERSONALITIES = [
  {
    id: 'friendly',
    name: 'Friendly',
    icon: Smile,
    description: 'Warm, encouraging, and uses casual language.',
    prompt: 'You are a friendly and approachable AI assistant. Use warm, conversational language. Be encouraging and supportive. Use casual expressions when appropriate.',
  },
  {
    id: 'professional',
    name: 'Professional',
    icon: Briefcase,
    description: 'Clear, concise, and maintains formal business etiquette.',
    prompt: 'You are a professional AI assistant. Maintain formal business etiquette. Be clear, concise, and precise in your responses. Focus on delivering accurate and actionable information.',
  },
  {
    id: 'expert',
    name: 'Expert',
    icon: GraduationCap,
    description: 'Technical, precise, and authoritative on complex topics.',
    prompt: 'You are an expert AI assistant with deep technical knowledge. Provide detailed, accurate, and authoritative responses. Use technical terminology appropriately and explain complex concepts clearly.',
  },
  {
    id: 'custom',
    name: 'Custom',
    icon: Settings2,
    description: 'Define your own unique voice and personality traits.',
    prompt: '',
  },
]

interface HumanContact {
  id: string
  name: string
  email: string
}

export default function CreateAgentPage() {
  const router = useRouter()
  const [currentStep, setCurrentStep] = useState(1)
  const [creating, setCreating] = useState(false)
  const [nameError, setNameError] = useState<string | null>(null)
  const [showTemplateSelector, setShowTemplateSelector] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<AgentTemplate | null>(null)
  const [humanContacts, setHumanContacts] = useState<HumanContact[]>([])

  // Get default personality prompt
  const defaultPersonality = PERSONALITIES.find(p => p.id === 'friendly')

  // Form data - initialize system_prompt with default personality prompt
  const [formData, setFormData] = useState({
    agent_type: 'LLM',
    name: '',
    description: '',
    avatar: '',
    system_prompt: defaultPersonality?.prompt || '',
    personality: 'friendly',
    suggestion_prompts: [] as any[],
    is_public: false,
    category: '',
    tags: '',
    human_contact_id: '',
    // LLM Configuration
    llm_provider: '',
    llm_model: '',
    llm_api_key: '',
    llm_api_base: '',
    temperature: 0.7,
    max_tokens: 4096,
    top_p: 1.0,
  })

  // Capabilities selection
  const [selectedCapabilities, setSelectedCapabilities] = useState<string[]>([])
  // OAuth apps selection for capabilities that require them
  const [selectedOAuthApps, setSelectedOAuthApps] = useState<Record<string, number>>({})

  // Fetch human contacts
  useEffect(() => {
    const fetchContacts = async () => {
      try {
        const contactsData = await apiClient.getHumanContacts()
        setHumanContacts(Array.isArray(contactsData) ? contactsData : [])
      } catch (error) {
        console.error('Failed to fetch contacts:', error)
      }
    }
    fetchContacts()
  }, [])

  // Handle personality change - pre-fill system prompt with preset text
  // But warn if user has custom content that would be lost
  const handlePersonalityChange = (newPersonality: string) => {
    const preset = PERSONALITIES.find(p => p.id === newPersonality)
    const currentPreset = PERSONALITIES.find(p => p.id === formData.personality)

    // Check if current system_prompt is custom (not matching any preset)
    const isCurrentPromptCustom = formData.system_prompt.trim() &&
      !PERSONALITIES.some(p => p.prompt === formData.system_prompt)

    if (isCurrentPromptCustom && newPersonality !== 'custom') {
      // User has custom content, confirm before overwriting
      if (!window.confirm('This will replace your current system prompt with the selected template. Continue?')) {
        return
      }
    }

    setFormData(prev => ({
      ...prev,
      personality: newPersonality,
      system_prompt: preset?.prompt || prev.system_prompt
    }))
  }

  const handleTemplateSelect = (template: AgentTemplate) => {
    setSelectedTemplate(template)
    setFormData(prev => ({
      ...prev,
      name: template.name.replace(/\s+/g, '_').toLowerCase(),
      description: template.description,
      system_prompt: template.systemPrompt,
      personality: 'custom',
      tags: template.tags.join(', '),
    }))
    setShowTemplateSelector(false)
    toast.success(`Template "${template.name}" applied!`)
  }

  const handleAvatarUpload = async (file: File): Promise<string> => {
    try {
      const response = await apiClient.uploadFile(file)
      const s3Uri = response.s3_uri || response.data?.s3_uri
      const displayUrl = response.url || response.data?.url

      if (s3Uri) {
        setFormData(prev => ({ ...prev, avatar: s3Uri }))
        toast.success('Avatar uploaded successfully')
        return displayUrl || s3Uri
      } else {
        throw new Error('Invalid response from server')
      }
    } catch (error) {
      console.error('Failed to upload avatar:', error)
      toast.error('Failed to upload avatar')
      throw error
    }
  }

  const handleAvatarRemove = async () => {
    setFormData(prev => ({ ...prev, avatar: '' }))
  }

  const validateStep = (step: number): boolean => {
    switch (step) {
      case 1:
        if (!formData.name.trim()) {
          toast.error('Please enter an agent name')
          return false
        }
        if (!formData.description.trim()) {
          toast.error('Please enter a description')
          return false
        }
        return true
      case 2:
        if (!formData.llm_provider) {
          toast.error('Please select an AI provider')
          return false
        }
        if (!formData.llm_model) {
          toast.error('Please select a model')
          return false
        }
        // API key is required
        if (!formData.llm_api_key.trim()) {
          toast.error('Please enter your API key')
          return false
        }
        return true
      case 3:
        if (!formData.system_prompt.trim()) {
          toast.error('Please enter a system prompt')
          return false
        }
        return true
      case 4:
        return true
      default:
        return true
    }
  }

  const nextStep = () => {
    if (validateStep(currentStep)) {
      setCurrentStep(prev => Math.min(prev + 1, STEPS.length))
    }
  }

  const prevStep = () => {
    setCurrentStep(prev => Math.max(prev - 1, 1))
  }

  const handleSubmit = async () => {
    setCreating(true)

    try {
      // Build LLM config with all fields (auto-generate config name)
      const llmConfig: any = {
        name: `Primary ${formData.llm_model}`,
        provider: formData.llm_provider,
        model_name: formData.llm_model,
        temperature: formData.temperature,
        max_tokens: formData.max_tokens,
        top_p: formData.top_p,
      }

      // Only include API key if provided
      if (formData.llm_api_key.trim()) {
        llmConfig.api_key = formData.llm_api_key.trim()
      }

      // Only include API base if provided
      if (formData.llm_api_base.trim()) {
        llmConfig.api_base = formData.llm_api_base.trim()
      }

      const data = await apiClient.createAgent({
        agent_type: formData.agent_type,
        is_public: formData.is_public,
        category: formData.is_public ? formData.category : null,
        tags: formData.is_public && formData.tags ? formData.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
        human_contact_id: formData.human_contact_id || null,
        config: {
          name: formData.name,
          description: formData.description,
          avatar: formData.avatar,
          system_prompt: formData.system_prompt,
          suggestion_prompts: formData.suggestion_prompts,
          tools: [],
          metadata: {},
          llm_config: llmConfig
        },
      })

      if (data.success) {
        const createdAgentId = data.data?.agent_id
        const createdAgentSlug = data.data?.slug || data.data?.agent_name || formData.name

        // Enable selected capabilities with OAuth apps
        if (selectedCapabilities.length > 0 && createdAgentId) {
          try {
            // Pass OAuth app IDs if any are selected
            const oauthAppIds = Object.keys(selectedOAuthApps).length > 0 ? selectedOAuthApps : undefined
            await apiClient.enableCapabilitiesBulk(createdAgentId, selectedCapabilities, oauthAppIds)
            toast.success(`Agent created with ${selectedCapabilities.length} capabilities!`)
          } catch (capError) {
            console.error('Failed to enable capabilities:', capError)
            toast.success('Agent created! Some capabilities could not be enabled.')
          }
        } else {
          toast.success('Agent created successfully!')
        }

        router.push(`/agents/${createdAgentSlug}/edit?tab=llm-models`)
      } else {
        toast.error('Failed to create agent: ' + data.message)
      }
    } catch (error: any) {
      console.error('Failed to create agent:', error)
      const errorMessage = error?.response?.data?.message
        || error?.response?.data?.detail
        || error?.data?.message
        || error?.data?.detail
        || error?.message
        || 'Failed to create agent'

      // If name conflict, go back to step 1 and show inline error on the name field
      if (error?.response?.status === 409 || errorMessage?.toLowerCase().includes('already exists')) {
        setNameError(errorMessage)
        setCurrentStep(1)
      }

      toast.error(errorMessage)
    } finally {
      setCreating(false)
    }
  }

  const progress = (currentStep / STEPS.length) * 100

  return (
    <div className="agent-workspace min-h-full px-4 py-4 md:px-8 md:py-6 xl:px-10">
      <div className="mx-auto max-w-[90rem] py-1">
        <div className="mb-4 flex items-center justify-between gap-4">
          <nav className="flex items-center gap-2 text-sm text-ash">
            <button
              onClick={() => router.push('/agents')}
              className="inline-flex items-center gap-1.5 transition-colors hover:text-ink"
            >
              <ArrowLeft size={14} />
              <span className="font-medium">Agents</span>
            </button>
            <span className="text-black/20">/</span>
            <span className="font-medium text-ink">Create Agent</span>
          </nav>
          <button
            onClick={() => setShowTemplateSelector(true)}
            className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-[13px] font-medium text-paper transition-transform motion-reduce:transition-none hover:-translate-y-0.5"
          >
            <Sparkles size={18} />
            <span className="font-medium">Use Template</span>
          </button>
        </div>

        {/* Progress Section */}
        <div className="dashboard-surface mb-6 rounded-[2rem] p-5 md:p-6">
          <div className="flex items-center justify-between mb-2">
            <div>
              <p className="text-[11px] font-semibold text-ash">Creation Wizard</p>
              <h2 className="text-[1.05rem] font-semibold text-ink md:text-[1.2rem]">
                Step {currentStep}: <span className="highlight-mint">{STEPS[currentStep - 1].name}</span>
              </h2>
            </div>
            <span className="text-sm text-ink-mute font-medium">{currentStep} of {STEPS.length}</span>
          </div>

          {/* Progress Bar */}
          <div className="h-2 bg-sand rounded-full overflow-hidden mb-4">
            <div
              className="h-full bg-ink hover:bg-ink/85 rounded-full transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Step Indicators */}
          <div className="flex justify-between">
            {STEPS.map((step, index) => (
              <button
                key={step.id}
                onClick={() => index < currentStep && setCurrentStep(step.id)}
                className={`flex flex-col items-center ${index < currentStep - 1 ? 'cursor-pointer' : 'cursor-default'}`}
              >
                <span className={`text-xs font-medium transition-colors ${
                  step.id === currentStep
                    ? 'text-primary-600'
                    : step.id < currentStep
                      ? 'text-leaf'
                      : 'text-ash'
                }`}>
                  {step.id < currentStep ? (
                    <span className="flex items-center gap-1">
                      <Check size={12} />
                      {step.name}
                    </span>
                  ) : step.name}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Step Content */}
        <div className="dashboard-panel overflow-hidden rounded-[2rem]">
          <div className="p-4 md:p-8">
            {currentStep === 1 && (
              <Step1Basics
                formData={formData}
                setFormData={setFormData}
                onAvatarUpload={handleAvatarUpload}
                onAvatarRemove={handleAvatarRemove}
                nameError={nameError}
                setNameError={setNameError}
              />
            )}
            {currentStep === 2 && (
              <Step2AIModel
                formData={formData}
                setFormData={setFormData}
              />
            )}
            {currentStep === 3 && (
              <Step3Personality
                formData={formData}
                setFormData={setFormData}
                onPersonalityChange={handlePersonalityChange}
              />
            )}
            {currentStep === 4 && (
              <Step5Review
                formData={formData}
                setFormData={setFormData}
                selectedCapabilities={selectedCapabilities}
                humanContacts={humanContacts}
              />
            )}
          </div>

          {/* Footer Navigation */}
          <div className="flex items-center justify-between border-t border-black/[0.08] bg-sand-deep px-6 py-4 md:px-8">
            <div>
              {currentStep > 1 && (
                <button
                  onClick={prevStep}
                  className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-medium text-ink-soft transition-colors hover:bg-white/50 hover:text-ink"
                >
                  <ArrowLeft size={18} />
                  Back
                </button>
              )}
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => router.push('/agents')}
                className="rounded-full px-5 py-2.5 text-[13px] font-medium text-ink-soft transition-colors hover:bg-white/50 hover:text-ink"
              >
                Cancel
              </button>

              {currentStep < STEPS.length ? (
                <button
                  onClick={nextStep}
                  className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-2.5 text-[13px] font-medium text-paper transition-transform motion-reduce:transition-none hover:-translate-y-0.5"
                >
                  Continue
                  <ArrowRight size={18} />
                </button>
              ) : (
                <button
                  onClick={handleSubmit}
                  disabled={creating}
                  className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-2.5 text-[13px] font-medium text-paper transition-transform motion-reduce:transition-none hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {creating ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full motion-safe:animate-spin" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <Check size={18} />
                      Create Agent
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Creator Tip */}
        <CreatorTip step={currentStep} />
      </div>

      {/* Template Selector Modal */}
      {showTemplateSelector && (
        <TemplateSelector
          onSelect={handleTemplateSelect}
          onClose={() => setShowTemplateSelector(false)}
        />
      )}
    </div>
  )
}

// Step 1: Basic Information (Bold UX)
function Step1Basics({ formData, setFormData, onAvatarUpload, onAvatarRemove, nameError, setNameError }: any) {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="mb-3 text-ink">Define <span className="highlight-mint">Your Agent</span></h1>
        <p className="max-w-3xl text-[15px] text-ink-soft">
          Give your AI agent an identity. A clear name and purpose helps users understand what it does.
        </p>
      </div>

      {/* Avatar and Name Row */}
      <div className="flex flex-col sm:flex-row items-start gap-6 sm:gap-8">
        <div className="flex-shrink-0">
          <label className="block text-sm font-bold text-ink mb-3">
            Avatar
          </label>
          <AvatarUpload
            currentAvatar={formData.avatar}
            onUpload={onAvatarUpload}
            onRemove={onAvatarRemove}
          />
        </div>

        <div className="flex-1 space-y-6">
          {/* Agent Name */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-bold text-ink">
                Agent Name *
              </label>
              <span className={`text-xs font-medium ${formData.name.length > 50 ? 'text-leaf' : 'text-ash'}`}>
                {formData.name.length}/50
              </span>
            </div>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => {
                setFormData({ ...formData, name: e.target.value.slice(0, 50) })
                if (nameError) setNameError(null)
              }}
              className={`w-full px-5 py-4 border-2 rounded-xl focus:ring-2 transition-[color,background-color,border-color,box-shadow,opacity,transform] bg-white text-lg font-medium ${
                nameError
                  ? 'border-hotpink focus:ring-blush focus:border-ink'
                  : 'border-line focus:ring-primary-500 focus:border-primary-500'
              }`}
              placeholder="e.g., Marketing Expert, Code Reviewer"
            />
            {nameError && (
              <p className="mt-2 text-sm text-danger flex items-center gap-1">
                <span></span> {nameError}
              </p>
            )}
          </div>

          {/* Agent Type */}
          <div>
            <label className="block text-sm font-bold text-ink mb-3">
              Agent Type
            </label>
            <div className="grid grid-cols-4 gap-3">
              {[
                { value: 'LLM', label: 'General', icon: Bot, desc: 'All-purpose assistant' },
                { value: 'RESEARCH', label: 'Research', icon: GraduationCap, desc: 'Deep analysis' },
                { value: 'CODE', label: 'Code', icon: Cpu, desc: 'Dev tasks' },
                { value: 'CLAUDE_CODE', label: 'Claude Code', icon: Zap, desc: 'Claude Agent SDK' },
              ].map((type) => (
                <button
                  key={type.value}
                  onClick={() => setFormData({ ...formData, agent_type: type.value })}
                  className={`relative p-4 rounded-2xl border-2 transition-[color,background-color,border-color,box-shadow,opacity,transform] text-left ${
                    formData.agent_type === type.value
                      ? 'border-black/15 bg-primary-50 shadow-soft'
                      : 'border-line hover:border-black/10 hover:shadow-md bg-white'
                  }`}
                >
                  <type.icon className={`w-6 h-6 mb-2 ${
                    formData.agent_type === type.value ? 'text-primary-600' : 'text-ash'
                  }`} />
                  <div className={`font-bold text-sm ${
                    formData.agent_type === type.value ? 'text-primary-900' : 'text-ink'
                  }`}>
                    {type.label}
                  </div>
                  <div className="text-xs text-ink-mute">{type.desc}</div>
                  {formData.agent_type === type.value && (
                    <div className="absolute top-2 right-2 w-5 h-5 bg-ink rounded-full flex items-center justify-center">
                      <Check size={12} className="text-white" />
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Description */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-bold text-ink">
            What does this agent do? *
          </label>
          <span className={`text-xs font-medium ${formData.description.length > 160 ? 'text-leaf' : 'text-ash'}`}>
            {formData.description.length}/160
          </span>
        </div>
        <textarea
          value={formData.description}
          onChange={(e) => setFormData({ ...formData, description: e.target.value.slice(0, 160) })}
          className="w-full px-5 py-4 border-2 border-line rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-[color,background-color,border-color,box-shadow,opacity,transform] bg-white text-base resize-none"
          rows={3}
          placeholder="Describe what your agent helps with…"
        />
        <p className="mt-2 text-sm text-ink-mute flex items-center gap-2">
          <Lightbulb size={14} className="text-warn" />
          Be specific! "Writes SEO blog posts" is better than "Helps with writing"
        </p>
      </div>
    </div>
  )
}

// Step 2: AI Model Configuration (Simplified & Bold UX)
function Step2AIModel({ formData, setFormData }: any) {
  const [providers, setProviders] = useState<ProviderPreset[]>([])
  const [models, setModels] = useState<ModelPreset[]>([])
  const [loadingProviders, setLoadingProviders] = useState(true)
  const [loadingModels, setLoadingModels] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)
  const [providerSearch, setProviderSearch] = useState('')
  const [modelSearch, setModelSearch] = useState('')

  const selectedProvider = providers.find(p => p.provider_id === formData.llm_provider)
  const selectedModel = models.find(m => m.model_name === formData.llm_model)

  // Filter providers based on search
  const filteredProviders = providers.filter(p =>
    p.provider_name.toLowerCase().includes(providerSearch.toLowerCase()) ||
    p.provider_id.toLowerCase().includes(providerSearch.toLowerCase())
  )

  // Filter models based on search
  const filteredModels = models.filter(m =>
    m.name.toLowerCase().includes(modelSearch.toLowerCase()) ||
    m.model_name.toLowerCase().includes(modelSearch.toLowerCase())
  )

  // Load providers on mount
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
    if (!formData.llm_provider) {
      setModels([])
      setLoadingModels(false)
      return
    }

    let cancelled = false

    const loadModels = async () => {
      try {
        setLoadingModels(true)
        const providerModels = await getProviderModels(formData.llm_provider)
        if (!cancelled) {
          setModels(providerModels)
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to load models:', error)
          toast.error('Failed to load models')
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
  }, [formData.llm_provider])

  const handleProviderSelect = (providerId: string) => {
    const provider = providers.find(p => p.provider_id === providerId)
    setFormData((prev: any) => ({
      ...prev,
      llm_provider: providerId,
      llm_model: '',
      llm_api_base: provider?.default_api_base || '',
    }))
    setModels([])
    setModelSearch('') // Clear model search when provider changes
  }

  const handleModelSelect = (modelName: string) => {
    const model = models.find(m => m.model_name === modelName)
    setFormData((prev: any) => ({
      ...prev,
      llm_model: modelName,
      // Use model defaults silently
      temperature: model?.default_temperature || 0.7,
      max_tokens: model?.default_max_tokens || 4096,
      top_p: 1.0,
    }))
  }

  if (loadingProviders) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="motion-safe:animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-ink-mute font-medium">Loading AI providers…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="mb-3 text-ink">Choose Your <span className="highlight-mint">AI Brain</span></h1>
        <p className="max-w-3xl text-[15px] text-ink-soft">
          Select the AI provider and model that will power your agent.
        </p>
      </div>

      {/* Step 1: Select Provider */}
      <div>
          <h2 className="mb-4 flex items-center gap-2 text-[1rem] font-semibold text-ink">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ink text-[12px] font-bold text-white">1</span>
            Select Provider
            <span className="text-sm font-normal text-ink-mute ml-2">({providers.length} available)</span>
          </h2>

        {/* Provider Search */}
        {providers.length > 6 && (
          <div className="mb-4">
            <input
              type="text"
              value={providerSearch}
              onChange={(e) => setProviderSearch(e.target.value)}
              placeholder="Search providers (e.g., OpenAI, LiteLLM, Ollama...)"
              className="w-full px-4 py-3 border-2 border-line rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white text-base"
            />
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-h-[400px] overflow-y-auto pr-1">
          {filteredProviders.map((provider) => (
            <button
              key={provider.provider_id}
              onClick={() => handleProviderSelect(provider.provider_id)}
              className={`relative p-4 rounded-2xl border-2 transition-[color,background-color,border-color,box-shadow,opacity,transform] text-left group ${
                formData.llm_provider === provider.provider_id
                  ? 'border-black/15 bg-primary-50 shadow-soft'
                  : 'border-line hover:border-black/10 hover:shadow-md bg-white'
              }`}
            >
              <div className="flex items-center gap-3">
                {(() => { const ProviderIcon = PROVIDER_ICONS[provider.provider_id] || PROVIDER_ICONS.default; return <ProviderIcon className="h-8 w-8" aria-hidden="true" /> })()}
                <div className="flex-1 min-w-0">
                  <div className={`font-bold text-base truncate ${
                    formData.llm_provider === provider.provider_id ? 'text-primary-900' : 'text-ink'
                  }`}>
                    {provider.provider_name}
                  </div>
                  <div className="text-xs text-ink-mute">
                    {provider.model_count || provider.models?.length || 0} models
                  </div>
                </div>
              </div>
              {formData.llm_provider === provider.provider_id && (
                <div className="absolute top-2 right-2 w-6 h-6 bg-ink rounded-full flex items-center justify-center">
                  <Check size={14} className="text-white" />
                </div>
              )}
            </button>
          ))}
        </div>
        {filteredProviders.length === 0 && providerSearch && (
          <p className="text-sm text-ink-mute mt-3 text-center py-4">
            No providers found matching "{providerSearch}"
          </p>
        )}
      </div>

      {/* Step 2: Select Model */}
      {formData.llm_provider && (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-300">
          <h2 className="mb-4 flex items-center gap-2 text-[1rem] font-semibold text-ink">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ink text-[12px] font-bold text-white">2</span>
            Select Model
            {models.length > 0 && (
              <span className="text-sm font-normal text-ink-mute ml-2">({models.length} available)</span>
            )}
          </h2>

          {loadingModels ? (
            <div className="flex items-center justify-center py-8 bg-cream rounded-2xl">
              <div className="motion-safe:animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              <span className="ml-3 text-ink-mute font-medium">Loading models…</span>
            </div>
          ) : models.length > 0 ? (
            <>
              {/* Model Search */}
              {models.length > 4 && (
                <div className="mb-4">
                  <input
                    type="text"
                    value={modelSearch}
                    onChange={(e) => setModelSearch(e.target.value)}
                    placeholder="Search models…"
                    className="w-full px-4 py-3 border-2 border-line rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white text-base"
                  />
                </div>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[560px] overflow-y-auto pr-1">
                {filteredModels.map((model, index) => {
                  const isSelected = formData.llm_model === model.model_name
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
                      onClick={() => handleModelSelect(model.model_name)}
                      className={`relative flex flex-col gap-0 rounded-2xl border-2 text-left transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-150 overflow-hidden ${
                        isSelected
                          ? 'border-black/15 shadow-soft'
                          : 'border-line bg-white hover:border-black/10 hover:shadow-md'
                      }`}
                    >
                      {/* Coloured top accent strip */}
                      <div className={`h-1 w-full ${isSelected ? 'bg-mint' : 'bg-transparent'}`} />

                      {/* Body */}
                      <div className={`flex-1 px-5 pt-4 pb-3 ${isSelected ? 'bg-primary-50' : ''}`}>

                        {/* Name row */}
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={`font-bold text-base leading-tight ${isSelected ? 'text-primary-900' : 'text-ink'}`}>
                              {model.name}
                            </span>
                            {index === 0 && !modelSearch && (
                              <span className="px-2 py-0.5 bg-leaf-wash text-forest text-xs font-semibold rounded-full">
                                Recommended
                              </span>
                            )}
                            {model.is_open_source && (
                              <span className="px-2 py-0.5 bg-sand-deep text-ink-soft text-xs font-semibold rounded-full">
                                Open Source
                              </span>
                            )}
                          </div>
                          {isSelected && (
                            <div className="shrink-0 w-6 h-6 bg-ink rounded-full flex items-center justify-center">
                              <Check size={13} className="text-white" />
                            </div>
                          )}
                        </div>

                        {/* Model ID */}
                        <p className="text-xs text-ash font-mono truncate mb-3">
                          {model.model_name}
                        </p>

                        {/* Description */}
                        <p className="text-sm text-ink-soft leading-relaxed line-clamp-2 mb-4">
                          {model.description}
                        </p>
                      </div>

                      {/* Metrics panel — always-visible footer */}
                      <div className={`grid grid-cols-3 divide-x border-t px-0 ${
                        isSelected
                          ? 'bg-primary-100/60 border-primary-200 divide-primary-200'
                          : 'bg-cream border-sand divide-sand'
                      }`}>

                        {/* Quality */}
                        <div className="px-4 py-3">
                          <p className="text-[10px] font-semibold text-ash mb-1.5">Quality</p>
                          {score !== null ? (
                            <>
                              <p className={`text-xl font-bold tabular-nums leading-none ${qualityTextColor}`}>
                                {score.toFixed(1)}
                              </p>
                              <div className="mt-1.5 h-1 w-full bg-line rounded-full overflow-hidden">
                                <div className={`h-full rounded-full ${qualityBarColor}`} style={{ width: `${qualityPct}%` }} />
                              </div>
                            </>
                          ) : (
                            <p className="text-sm text-ash">—</p>
                          )}
                        </div>

                        {/* Speed */}
                        <div className="px-4 py-3">
                          <p className="text-[10px] font-semibold text-ash mb-1.5">Speed</p>
                          {model.speed_tier ? (
                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold ${
                              model.speed_tier === 'fast'   ? 'bg-leaf-wash text-forest' :
                              model.speed_tier === 'medium' ? 'bg-sand-deep text-gold' :
                                                              'bg-blush-wash text-leaf'
                            }`}>
                              {model.speed_tier === 'fast' && <Zap className="w-3 h-3" />}
                              {model.speed_tier.charAt(0).toUpperCase() + model.speed_tier.slice(1)}
                            </span>
                          ) : (
                            <p className="text-sm text-ash">—</p>
                          )}
                        </div>

                        {/* Cost */}
                        <div className="px-4 py-3">
                          <p className="text-[10px] font-semibold text-ash mb-1.5">Cost / 1M</p>
                          {model.cost_input_per_1m === null ? (
                            <p className="text-sm text-ash">—</p>
                          ) : model.cost_input_per_1m === 0 ? (
                            <p className="text-sm font-bold text-leaf">Free</p>
                          ) : (
                            <>
                              <p className="text-sm font-bold text-ink tabular-nums leading-tight">
                                ${model.cost_input_per_1m}
                              </p>
                              <p className="text-xs text-ash tabular-nums mt-0.5">
                                ${model.cost_output_per_1m} out
                              </p>
                            </>
                          )}
                        </div>

                      </div>
                    </button>
                  )
                })}
              </div>
              {filteredModels.length === 0 && modelSearch && (
                <p className="text-sm text-ink-mute mt-3 text-center py-4">
                  No models found matching "{modelSearch}"
                </p>
              )}
            </>
          ) : (
            <div className="text-center py-8 bg-cream rounded-2xl text-ink-mute">
              No models available for this provider
            </div>
          )}
        </div>
      )}

      {/* Step 3: API Key (always required) */}
      {formData.llm_model && (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-300">
          <h2 className="mb-4 flex items-center gap-2 text-[1rem] font-semibold text-ink">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ink text-[12px] font-bold text-white">3</span>
            Enter API Key
            <span className="text-leaf">*</span>
          </h2>

          <div className="bg-cream rounded-2xl p-6">
            <div className="relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={formData.llm_api_key}
                onChange={(e) => setFormData({ ...formData, llm_api_key: e.target.value })}
                placeholder={`Paste your ${selectedProvider?.provider_name || 'provider'} API key here`}
                className={`w-full px-5 py-4 border-2 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white text-base font-medium pr-24 ${
                  formData.llm_api_key ? 'border-mint' : 'border-line'
                }`}
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-sm font-semibold text-primary-600 hover:text-primary-700"
              >
                {showApiKey ? 'Hide' : 'Show'}
              </button>
            </div>

            {selectedProvider?.setup_instructions && (
              <div className="mt-3 flex items-start gap-2 text-sm text-ink-soft">
                <Lightbulb size={16} className="text-warn mt-0.5 flex-shrink-0" />
                <span>{selectedProvider.setup_instructions}</span>
              </div>
            )}

            {formData.llm_api_key && (
              <div className="mt-4 p-3 bg-leaf-wash border border-mint rounded-xl flex items-center gap-2">
                <Check size={16} className="text-leaf" />
                <p className="text-sm text-forest font-medium">
                  API key entered
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* API Base URL for special providers */}
      {selectedProvider && selectedProvider.requires_api_base && formData.llm_model && (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-300">
          <h2 className="text-lg font-bold text-ink mb-4 flex items-center gap-2">
            <span className="w-7 h-7 bg-ash text-white rounded-full flex items-center justify-center text-sm font-bold">+</span>
            API Endpoint
          </h2>
          <input
            type="url"
            value={formData.llm_api_base}
            onChange={(e) => setFormData({ ...formData, llm_api_base: e.target.value })}
            placeholder={selectedProvider.default_api_base || 'https://api.example.com/v1'}
            className="w-full px-5 py-4 border-2 border-line rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white text-base"
          />
        </div>
      )}

      {/* Selection Summary */}
      {formData.llm_provider && formData.llm_model && (
        <div className={`rounded-2xl p-5 border-2 ${
          formData.llm_api_key
            ? 'bg-leaf-wash border-mint'
            : 'bg-ink hover:bg-ink/85 border-primary-200'
        }`}>
          <div className="flex items-center gap-4">
            {(() => { const ProviderIcon = PROVIDER_ICONS[formData.llm_provider] || PROVIDER_ICONS.default; return <ProviderIcon className="h-10 w-10" aria-hidden="true" /> })()}
            <div className="flex-1">
              <div className={`text-[11px] font-semibold ${
                formData.llm_api_key ? 'text-leaf' : 'text-primary-600'
              }`}>
                {formData.llm_api_key ? 'Ready to Go!' : 'Almost There'}
              </div>
              <div className="text-[1.15rem] font-semibold text-ink">{selectedProvider?.provider_name} / {selectedModel?.name}</div>
            </div>
            {formData.llm_api_key ? (
              <div className="flex items-center gap-2 px-4 py-2 bg-leaf text-white rounded-full text-sm font-bold shadow-lg shadow-green-500/30">
                <Check size={16} /> Complete
              </div>
            ) : (
              <div className="flex items-center gap-2 px-4 py-2 bg-sand-deep text-gold rounded-full text-sm font-bold">
                Enter API Key
              </div>
            )}
          </div>
        </div>
      )}

    </div>
  )
}

// Step 3: Personality & Tone (Bold UX)
function Step3Personality({ formData, setFormData, onPersonalityChange }: {
  formData: any
  setFormData: any
  onPersonalityChange: (personality: string) => void
}) {
  const selectedPersonality = PERSONALITIES.find(p => p.id === formData.personality)

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="mb-3 text-ink">Set the <span className="highlight-pink">Tone</span></h1>
        <p className="max-w-3xl text-[15px] text-ink-soft">
          Pick a starting personality, then customize the system prompt as needed.
        </p>
      </div>

      {/* Personality Options - Horizontal layout */}
      <div>
        <label className="block text-sm font-bold text-ink mb-3">Start with a Personality Template</label>
        <div className="grid grid-cols-4 gap-3">
          {PERSONALITIES.map((personality) => (
            <button
              key={personality.id}
              onClick={() => onPersonalityChange(personality.id)}
              className={`p-4 rounded-2xl border-2 transition-[color,background-color,border-color,box-shadow,opacity,transform] text-left relative ${
                formData.personality === personality.id
                  ? 'border-black/15 bg-blush-wash shadow-soft'
                  : 'border-line hover:border-black/10 hover:shadow-md bg-white'
              }`}
            >
              {formData.personality === personality.id && (
                <div className="absolute top-2 right-2 w-5 h-5 bg-ink rounded-full flex items-center justify-center">
                  <Check size={12} className="text-white" />
                </div>
              )}
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-2 ${
                formData.personality === personality.id
                  ? 'bg-blush-wash'
                  : 'bg-sand'
              }`}>
                <personality.icon className={`w-5 h-5 ${
                  formData.personality === personality.id
                    ? 'text-ink'
                    : 'text-ink-mute'
                }`} />
              </div>
              <div className={`font-bold text-sm mb-1 ${
                formData.personality === personality.id
                  ? 'text-primary-900'
                  : 'text-ink'
              }`}>
                {personality.name}
              </div>
              <div className="text-xs text-ink-mute leading-relaxed line-clamp-2">
                {personality.description}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* System Prompt and Preview in 2 columns */}
      <div className="grid grid-cols-5 gap-6">
        {/* System Prompt - Takes 3 columns */}
        <div className="col-span-3">
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-bold text-ink">
              System Prompt
            </label>
            <span className="text-xs text-ink-mute">
              Currently: {selectedPersonality?.name} template
            </span>
          </div>
          <textarea
            value={formData.system_prompt}
            onChange={(e) => setFormData((prev: any) => ({ ...prev, system_prompt: e.target.value }))}
            className="w-full px-5 py-4 border-2 border-line rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-[color,background-color,border-color,box-shadow,opacity,transform] bg-white font-mono text-sm"
            rows={12}
            placeholder="You are a helpful AI assistant...

Define your agent's personality, behavior, and capabilities here. Be specific about:
- How the agent should respond
- What tone to use
- Any specific rules or guidelines
- Knowledge domains or expertise areas"
          />
          <p className="mt-2 text-xs text-ink-mute">
            This is the complete system prompt for your agent. Select a personality template above to pre-fill, then edit as needed.
          </p>
        </div>

        {/* Visual Preview - Takes 2 columns */}
        <div className="col-span-2">
            <div className="bg-cream rounded-xl p-5 sticky top-4 border border-black/[0.08]">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-2 h-2 bg-leaf rounded-full motion-safe:animate-pulse" />
              <span className="text-sm font-medium text-ink-soft">Live Preview</span>
            </div>

            <div className="space-y-3 mb-4">
              {/* User Message */}
              <div className="flex justify-end">
                <div className="bg-white rounded-2xl rounded-tr-md px-3 py-2 max-w-[85%] shadow-sm border border-sand">
                  <p className="text-xs text-ink-soft">Hey there! I need help setting up my first project.</p>
                </div>
              </div>

              {/* Agent Response */}
              <div className="flex justify-start">
                <div className="bg-primary-50 rounded-2xl rounded-tl-md px-3 py-2 max-w-[85%] border border-primary-100">
                  <p className="text-[10px] font-medium text-primary-600 mb-1">Agent</p>
                  <p className="text-xs text-ink-soft">
                    {selectedPersonality?.id === 'friendly' && "I'd be absolutely thrilled to help you get started! Let's do this together, step by step."}
                    {selectedPersonality?.id === 'professional' && "I'll be happy to assist you with your project setup. Please provide the specific requirements."}
                    {selectedPersonality?.id === 'expert' && "Certainly. Let's begin with the foundational aspects. I'll need to understand your requirements first."}
                    {selectedPersonality?.id === 'custom' && "I'm here to help! Let me know what you need assistance with."}
                  </p>
                </div>
              </div>
            </div>

            {/* Personality Label */}
            <div className="text-center p-3 bg-ink hover:bg-ink/85 rounded-xl border border-black/[0.06]">
              <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center mx-auto mb-2 shadow-sm">
                {selectedPersonality && <selectedPersonality.icon className="w-5 h-5 text-primary-600" />}
              </div>
              <p className="text-sm font-semibold text-primary-900">
                {selectedPersonality?.name}
              </p>
              <p className="text-xs text-primary-600">
                personality selected
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Step 4: Capabilities (Bold UX)
function Step4Capabilities({
  selectedCapabilities,
  onCapabilitiesChange,
  selectedOAuthApps,
  onOAuthAppsChange
}: {
  selectedCapabilities: string[]
  onCapabilitiesChange: (capabilityIds: string[]) => void
  selectedOAuthApps: Record<string, number>
  onOAuthAppsChange: (oauthApps: Record<string, number>) => void
}) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="mb-3 text-ink">Add <span className="highlight-mint">Superpowers</span></h1>
        <p className="max-w-3xl text-[15px] text-ink-soft">
          Select capabilities to unlock powerful tools and integrations for your agent.
        </p>
      </div>

      <CapabilitySelector
        selectedCapabilities={selectedCapabilities}
        onCapabilitiesChange={onCapabilitiesChange}
        selectedOAuthApps={selectedOAuthApps}
        onOAuthAppsChange={onOAuthAppsChange}
        showPresets={true}
        compact={false}
      />

      {selectedCapabilities.length > 0 && (
        <div className="p-5 bg-leaf-wash border-2 border-mint rounded-2xl">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-leaf rounded-full flex items-center justify-center">
              <Check className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-forest text-lg">
                {selectedCapabilities.length} capability{selectedCapabilities.length !== 1 ? 'ies' : ''} selected
              </span>
              <p className="text-sm text-forest">
                These will be enabled automatically when your agent is created.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Step 5: Review & Create
function Step5Review({ formData, setFormData, selectedCapabilities, humanContacts }: any) {
  const selectedPersonality = PERSONALITIES.find(p => p.id === formData.personality)
  const [providerName, setProviderName] = useState(formData.llm_provider)

  // Fetch provider name for display
  useEffect(() => {
    const fetchProviderName = async () => {
      try {
        const providers = await getLLMProviders()
        const provider = providers.find(p => p.provider_id === formData.llm_provider)
        if (provider) {
          setProviderName(provider.provider_name)
        }
      } catch (error) {
        // Use provider_id as fallback
      }
    }
    if (formData.llm_provider) {
      fetchProviderName()
    }
  }, [formData.llm_provider])

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="mb-3 text-ink">Ready to <span className="highlight-pink">Launch</span></h1>
        <p className="max-w-3xl text-[15px] text-ink-soft">
          Review your agent configuration. You can always edit these later.
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-6">
        {/* Basic Info Card */}
        <div className="p-5 bg-cream rounded-2xl border border-line">
          <h3 className="font-bold text-ink mb-4 flex items-center gap-2">
            <User className="w-5 h-5 text-primary-600" />
            Basic Info
          </h3>
          <div className="space-y-3">
            <div>
              <div className="text-xl font-bold text-ink">{formData.name || '-'}</div>
              <div className="text-sm text-ink-mute">{formData.agent_type} Agent</div>
            </div>
            <p className="text-sm text-ink-soft">{formData.description || '-'}</p>
          </div>
        </div>

        {/* AI Model Card */}
        <div className="p-5 bg-cream rounded-2xl border border-line">
          <h3 className="font-bold text-ink mb-4 flex items-center gap-2">
            <Cpu className="w-5 h-5 text-primary-600" />
            AI Model
          </h3>
          <div className="flex items-center gap-4">
            {(() => { const ProviderIcon = PROVIDER_ICONS[formData.llm_provider] || PROVIDER_ICONS.default; return <ProviderIcon className="h-10 w-10" aria-hidden="true" /> })()}
            <div className="flex-1">
              <div className="font-bold text-ink text-lg">{providerName}</div>
              <div className="text-sm text-ink-mute">{formData.llm_model}</div>
            </div>
            <span className="px-3 py-1.5 bg-leaf-wash text-forest rounded-full text-xs font-bold flex items-center gap-1">
              <Check size={12} /> Configured
            </span>
          </div>
        </div>

        {/* Personality Card */}
        <div className="p-5 bg-cream rounded-2xl border border-line">
          <h3 className="font-bold text-ink mb-4 flex items-center gap-2">
            <Smile className="w-5 h-5 text-primary-600" />
            Personality
          </h3>
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-sand-deep rounded-xl flex items-center justify-center">
              {selectedPersonality && <selectedPersonality.icon className="w-6 h-6 text-primary-600" />}
            </div>
            <div>
              <div className="font-bold text-ink text-lg">{selectedPersonality?.name}</div>
              <div className="text-sm text-ink-mute">{selectedPersonality?.description}</div>
            </div>
          </div>
        </div>

        {/* Capabilities Card */}
        <div className="p-5 bg-cream rounded-2xl border border-line">
          <h3 className="font-bold text-ink mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5 text-primary-600" />
            Capabilities
          </h3>
          {selectedCapabilities.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {selectedCapabilities.slice(0, 6).map((cap: string) => (
                <span key={cap} className="px-3 py-1.5 bg-primary-100 text-primary-700 rounded-lg text-xs font-bold">
                  {cap.replace(/_/g, ' ')}
                </span>
              ))}
              {selectedCapabilities.length > 6 && (
                <span className="px-3 py-1.5 bg-line text-ink-soft rounded-lg text-xs font-bold">
                  +{selectedCapabilities.length - 6} more
                </span>
              )}
            </div>
          ) : (
            <p className="text-sm text-ink-mute italic">No capabilities selected</p>
          )}
        </div>

        {/* Advanced Settings Card */}
        <div className="p-5 bg-cream rounded-2xl border border-line">
          <h3 className="font-bold text-ink mb-4 flex items-center gap-2">
            <Settings2 className="w-5 h-5 text-primary-600" />
            Settings
          </h3>

          {/* Marketplace Toggle */}
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm text-ink-soft">List in Marketplace</span>
            <button
              onClick={() => setFormData({ ...formData, is_public: !formData.is_public })}
              className={`relative w-11 h-6 rounded-full transition-colors ${
                formData.is_public ? 'bg-primary-500' : 'bg-taupe'
              }`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform motion-reduce:transition-none ${
                formData.is_public ? 'translate-x-5' : 'translate-x-0'
              }`} />
            </button>
          </div>

          {formData.is_public && (
            <div className="space-y-3 pt-3 border-t border-line">
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Category</label>
                <select
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  className="w-full px-3 py-2 border border-line rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                >
                  <option value="">Select category</option>
                  <option value="Productivity">Productivity</option>
                  <option value="Research">Research</option>
                  <option value="Development">Development</option>
                  <option value="Writing">Writing</option>
                  <option value="Data Analysis">Data Analysis</option>
                  <option value="Customer Support">Customer Support</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Tags</label>
                <input
                  type="text"
                  value={formData.tags}
                  onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                  className="w-full px-3 py-2 border border-line rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder="e.g., automation, productivity"
                />
              </div>
            </div>
          )}

          {/* Human Contact */}
          <div className="mt-4 pt-4 border-t border-line">
            <label className="block text-xs font-medium text-ink-soft mb-1">Human Escalation Contact</label>
            <select
              value={formData.human_contact_id}
              onChange={(e) => setFormData({ ...formData, human_contact_id: e.target.value })}
              className="w-full px-3 py-2 border border-line rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            >
              <option value="">No escalation contact</option>
              {humanContacts?.map((contact: any) => (
                <option key={contact.id} value={contact.id}>
                  {contact.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Next Steps Info */}
      <div className="p-5 bg-sky-wash border border-sky-wash rounded-2xl">
        <h4 className="font-bold text-azure mb-3">After creating your agent</h4>
        <ul className="text-sm text-azure space-y-2">
          <li className="flex items-center gap-3">
            <span className="w-2 h-2 bg-azure rounded-full" />
            Upload skills and context documents
          </li>
          <li className="flex items-center gap-3">
            <span className="w-2 h-2 bg-azure rounded-full" />
            Connect knowledge bases for enhanced responses
          </li>
          <li className="flex items-center gap-3">
            <span className="w-2 h-2 bg-azure rounded-full" />
            Test your agent in the chat interface
          </li>
        </ul>
      </div>
    </div>
  )
}

// Creator Tips Component
function CreatorTip({ step }: { step: number }) {
  const tips = {
    1: {
      title: 'Creator Tip',
      content: 'Use action-oriented words in your description. Agents with clear, specific benefits see 40% higher engagement in the marketplace.',
    },
    2: {
      title: 'Model Selection',
      content: 'GPT-4o and Claude Sonnet 4 are great all-rounders. For cost-sensitive apps, consider GPT-4o Mini or Groq\'s fast Llama models.',
    },
    3: {
      title: 'Personality Matters',
      content: 'Matching your agent\'s tone to your audience builds trust. Professional for B2B, friendly for consumer apps.',
    },
    4: {
      title: 'Start Small',
      content: 'Begin with essential capabilities and add more later. This helps you understand which tools your users actually need.',
    },
    5: {
      title: 'Almost There!',
      content: 'Review your configuration and create your agent. You can always edit these settings later from the agent\'s edit page.',
    },
  }

  const tip = tips[step as keyof typeof tips]

  return (
    <div className="mt-6 rounded-[1.4rem] border border-primary-200 bg-ink hover:bg-ink/85/50 p-5">
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-ink text-white">
          <Lightbulb className="w-4 h-4" />
        </div>
        <div>
          <h4 className="mb-1 text-[14px] font-semibold text-primary-900">{tip.title}</h4>
          <p className="text-[13px] text-primary-800">{tip.content}</p>
        </div>
      </div>
    </div>
  )
}
