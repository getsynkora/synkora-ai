'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import toast from 'react-hot-toast'
import { Info, Wrench, Settings, FileText, Activity, Zap, X, Sparkles, Link, Globe, DollarSign, Tag, Users, Mail, ExternalLink, Trash2 } from 'lucide-react'
import {
  listEmailTemplates,
  getAgentEmailTemplate,
  assignEmailTemplate,
  removeEmailTemplate,
  type EmailTemplate,
} from '@/lib/api/email-templates'
import IntegrationsTab from '@/components/agents/integrations/IntegrationsTab'
import ContextFilesUpload from '@/components/agents/ContextFilesUpload'
import { apiClient } from '@/lib/api/client'
import { AvatarUpload } from '@/components/profile/AvatarUpload'
import PerformanceConfig from '@/components/agents/PerformanceConfig'
import { LLMConfigForm, LLMConfigList } from '@/components/agents/llm-configs'
import { useLLMConfigManager } from '@/hooks/useAgentLLMConfigs'
import { AgentLLMConfig, AgentLLMConfigCreate, AgentLLMConfigUpdate } from '@/types/agent-llm-config'

interface HumanContact {
  id: string
  name: string
  email: string
}

type Tab = 'general' | 'llm-models' | 'context' | 'vision' | 'observability' | 'multi-agent' | 'performance' | 'advanced' | 'integrations' | 'landing-page' | 'email'

export default function EditAgentPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const agentName = params.agentName as string

  // Read initial tab from URL query params, default to 'general'
  const initialTab = (searchParams.get('tab') as Tab) || 'general'
  const [activeTab, setActiveTab] = useState<Tab>(initialTab)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [humanContacts, setHumanContacts] = useState<HumanContact[]>([])

  // Form data
  const [formData, setFormData] = useState({
    agent_type: 'LLM',
    name: '',
    description: '',
    avatar: '',
    system_prompt: '',
    suggestion_prompts: '',  // Changed to string for JSON input
    api_key: '',
    provider: 'google',
    temperature: 0.7,
    model_name: 'gemini-2.0-flash-exp',
    api_base: '',
    max_tokens: 4096,
    top_p: 1.0,
    extra_headers: '',
    is_public: false,
    portal_visibility: 'hidden',
    category: '',
    tags: '',
    human_contact_id: '',
  })
  
  // Observability config
  const [observabilityConfig, setObservabilityConfig] = useState({
    langfuse_enabled: false,
    sample_rate: 1.0,
    trace_tools: true,
    trace_rag: true,
    langfuse_host: '',
    langfuse_public_key: '',
    langfuse_secret_key: '',
  })

  // Multi-agent config
  const [multiAgentConfig, setMultiAgentConfig] = useState({
    allow_transfer: false,
    transfer_scope: 'sub_agents',
  })

  // Performance config
  const [performanceConfig, setPerformanceConfig] = useState<any>(null)

  // Agentic execution config
  const [agenticConfig, setAgenticConfig] = useState({
    max_iterations: 100,
    tool_retry_attempts: 2,
    parallel_tools: true,
  })

  // Execution backend
  const [executionBackend, setExecutionBackend] = useState<'celery' | 'lambda' | 'cloud_run' | 'do_functions'>('celery')
  const [hasServerlessExecution, setHasServerlessExecution] = useState(false)

  // PII redaction config
  const [piiRedactionConfig, setPiiRedactionConfig] = useState({
    redact_for_llm: false,
    redact_for_response: false,
    patterns: ['email', 'phone', 'ssn', 'credit_card', 'ip_address'],
  })

  // Integrations config (MCP server + A2A)
  const [integrationsConfig, setIntegrationsConfig] = useState<any>({})

  // Email template assignment
  const [assignedTemplate, setAssignedTemplate] = useState<EmailTemplate | null>(null)
  const [allTemplates, setAllTemplates] = useState<EmailTemplate[]>([])
  const [emailTabLoading, setEmailTabLoading] = useState(false)
  const [emailTabSaving, setEmailTabSaving] = useState(false)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')

  // Image generation LLM config ID (stored in agent_metadata)
  const [imageGenLlmConfigId, setImageGenLlmConfigId] = useState<string>('')
  const [agentLlmConfigs, setAgentLlmConfigs] = useState<AgentLLMConfig[]>([])

  // Store the agent ID (not the name) for integrations endpoints
  const [agentId, setAgentId] = useState<string>('')

  // Store original agent_metadata to preserve other fields
  const [originalAgentMetadata, setOriginalAgentMetadata] = useState<any>({})

  useEffect(() => {
    fetchAgentDetails()
    fetchContacts()
    fetchPlanFeatures()
    fetchAgentLlmConfigs()
    fetchEmailTemplateData()
  }, [agentName])

  const fetchPlanFeatures = async () => {
    try {
      const data = await apiClient.request('GET', '/api/v1/usage-stats')
      const features = data?.limits?.features || {}
      setHasServerlessExecution(features.serverless_execution === true)
    } catch {
      // Non-fatal: default to false (no serverless access)
    }
  }

  const fetchAgentLlmConfigs = async () => {
    try {
      const configs = await apiClient.getAgentLLMConfigs(agentName)
      setAgentLlmConfigs(Array.isArray(configs) ? configs : [])
    } catch (error) {
      console.error('Failed to fetch agent LLM configs:', error)
    }
  }

  const fetchContacts = async () => {
    try {
      const contactsData = await apiClient.getHumanContacts()
      setHumanContacts(Array.isArray(contactsData) ? contactsData : [])
    } catch (error) {
      console.error('Failed to fetch contacts:', error)
    }
  }

  const fetchEmailTemplateData = async () => {
    try {
      const [templates, assigned] = await Promise.all([
        listEmailTemplates(),
        getAgentEmailTemplate(agentName).catch(() => null),
      ])
      setAllTemplates(templates)
      setAssignedTemplate(assigned)
      setSelectedTemplateId(assigned?.id ?? '')
    } catch (error) {
      console.error('Failed to fetch email template data:', error)
    }
  }

  const handleAssignTemplate = async () => {
    if (!selectedTemplateId) return
    setEmailTabSaving(true)
    try {
      const updated = await assignEmailTemplate(agentName, selectedTemplateId)
      setAssignedTemplate(updated)
      toast.success('Email template assigned')
    } catch (e: any) {
      toast.error(e.message || 'Failed to assign template')
    } finally {
      setEmailTabSaving(false)
    }
  }

  const handleRemoveTemplate = async () => {
    if (!confirm('Remove the assigned email template from this agent?')) return
    setEmailTabSaving(true)
    try {
      await removeEmailTemplate(agentName)
      setAssignedTemplate(null)
      setSelectedTemplateId('')
      toast.success('Email template removed')
    } catch (e: any) {
      toast.error(e.message || 'Failed to remove template')
    } finally {
      setEmailTabSaving(false)
    }
  }

  const fetchAgentDetails = async () => {
    try {
      setLoading(true)
      const agent = await apiClient.getAgent(agentName)

      // Extract extra headers from additional_params if present
      let extraHeadersStr = ''
      if (agent.llm_config.additional_params?.extra_headers) {
        extraHeadersStr = JSON.stringify(agent.llm_config.additional_params.extra_headers, null, 2)
      }
      
      // Convert suggestion_prompts to JSON string for editing
      let suggestionPromptsStr = ''
      if (agent.suggestion_prompts && agent.suggestion_prompts.length > 0) {
        suggestionPromptsStr = JSON.stringify(agent.suggestion_prompts, null, 2)
      }
      
      setFormData({
        agent_type: agent.agent_type?.toUpperCase() || 'LLM',
        name: agent.agent_name,
        description: agent.description || '',
        avatar: agent.avatar || '',
        system_prompt: agent.system_prompt || '',
        suggestion_prompts: suggestionPromptsStr,
        api_key: agent.llm_config.api_key || '',
        provider: agent.llm_config.provider || 'google',
        temperature: agent.llm_config.temperature || 0.7,
        model_name: agent.llm_config.model || agent.llm_config.model_name || 'gemini-2.0-flash-exp',
        api_base: agent.llm_config.api_base || '',
        max_tokens: agent.llm_config.max_tokens || 4096,
        top_p: agent.llm_config.top_p || 1.0,
        extra_headers: extraHeadersStr,
        is_public: agent.is_public || false,
        portal_visibility: agent.portal_visibility || 'hidden',
        category: agent.category || '',
        tags: agent.tags ? agent.tags.join(', ') : '',
        human_contact_id: agent.human_contact_id || '',
      })

      // Set multi-agent config
      setMultiAgentConfig({
        allow_transfer: agent.allow_transfer || false,
        transfer_scope: agent.transfer_scope || 'sub_agents',
      })

      // Store agent UUID for integrations tab endpoints
      setAgentId(agent.id || '')

      // Store original agent_metadata to preserve all fields
      setOriginalAgentMetadata(agent.agent_metadata || {})
      
      // Set performance config from agent_metadata
      if (agent.agent_metadata?.performance_config) {
        setPerformanceConfig(agent.agent_metadata.performance_config)
      }

      // Set integrations config from agent_metadata
      if (agent.agent_metadata?.integrations_config) {
        setIntegrationsConfig(agent.agent_metadata.integrations_config)
      }

      // Set execution backend (top-level field)
      if (agent.execution_backend) {
        setExecutionBackend(agent.execution_backend as 'celery' | 'lambda' | 'cloud_run' | 'do_functions')
      }
      // Set agentic config from agent_metadata
      if (agent.agent_metadata?.agentic_config) {
        const ac = agent.agent_metadata.agentic_config
        setAgenticConfig({
          max_iterations: ac.max_iterations ?? 100,
          tool_retry_attempts: ac.tool_retry_attempts ?? 2,
          parallel_tools: ac.parallel_tools ?? true,
        })
      }

      // Set PII redaction config from agent_metadata
      if (agent.agent_metadata?.pii_redaction) {
        const pii = agent.agent_metadata.pii_redaction
        setPiiRedactionConfig({
          redact_for_llm: pii.redact_for_llm ?? false,
          redact_for_response: pii.redact_for_response ?? false,
          patterns: pii.patterns ?? ['email', 'phone', 'ssn', 'credit_card', 'ip_address'],
        })
      }

      // Set image generation LLM config ID from agent_metadata
      setImageGenLlmConfigId(agent.agent_metadata?.image_generation_llm_config_id || '')

      // Set observability config - handle both null and existing config
      if (agent.observability_config) {
        setObservabilityConfig({
          langfuse_enabled: agent.observability_config.langfuse_enabled === true,
          sample_rate: agent.observability_config.sample_rate ?? 1.0,
          trace_tools: agent.observability_config.trace_tools !== false,
          trace_rag: agent.observability_config.trace_rag !== false,
          langfuse_host: agent.observability_config.langfuse_host || '',
          langfuse_public_key: agent.observability_config.langfuse_public_key || '',
          langfuse_secret_key: agent.observability_config.langfuse_secret_key || '',
        })
      } else {
        // Set default values if no observability config exists
        setObservabilityConfig({
          langfuse_enabled: false,
          sample_rate: 1.0,
          trace_tools: true,
          trace_rag: true,
          langfuse_host: '',
          langfuse_public_key: '',
          langfuse_secret_key: '',
        })
      }
    } catch (error) {
      console.error('Failed to fetch agent details:', error)
      toast.error('Failed to load agent details')
    } finally {
      setLoading(false)
    }
  }

  const handleAvatarUpload = async (file: File) => {
    try {
      const response = await apiClient.uploadAgentAvatar(agentName, file)
      // Backend already updates the agent avatar in database with S3 URI during upload
      // Refetch agent details to get the latest avatar URL (backend converts S3 URI to presigned URL)
      await fetchAgentDetails()
      toast.success('Avatar uploaded and updated successfully')
      // Return the display URL from the upload response for immediate preview
      return response.url || response.data?.url || response.data?.http_url
    } catch (error) {
      console.error('Failed to upload avatar:', error)
      toast.error('Failed to upload avatar')
      throw error
    }
  }

  const handleAvatarRemove = async () => {
    setFormData(prev => ({ ...prev, avatar: '' }))
  }

  const handleSubmit = async () => {
    setSaving(true)

    try {
      // Parse extra headers if provided
      const additionalParams: any = {}
      if (formData.extra_headers.trim()) {
        try {
          const parsedHeaders = JSON.parse(formData.extra_headers)
          additionalParams.extra_headers = parsedHeaders
        } catch {
          toast.error('Invalid JSON in Extra Headers field')
          setSaving(false)
          return
        }
      }

      // Parse suggestion prompts if provided
      let suggestionPrompts: any[] = []
      if (formData.suggestion_prompts.trim()) {
        try {
          suggestionPrompts = JSON.parse(formData.suggestion_prompts)
          if (!Array.isArray(suggestionPrompts)) {
            toast.error('Suggestion prompts must be a JSON array')
            setSaving(false)
            return
          }
        } catch {
          toast.error('Invalid JSON in Suggestion Prompts field')
          setSaving(false)
          return
        }
      }

      // Build agent_metadata - merge with original to preserve other fields
      const agentMetadata: any = {
        ...originalAgentMetadata,
        performance_config: performanceConfig,
        agentic_config: agenticConfig,
        integrations_config: integrationsConfig,
        pii_redaction: piiRedactionConfig,
        ...(imageGenLlmConfigId ? { image_generation_llm_config_id: imageGenLlmConfigId } : {}),
      }

      const updateResponse = await apiClient.updateAgent(agentName, {
        name: formData.name !== agentName ? formData.name : undefined,
        description: formData.description,
        // Avatar is handled separately by uploadAgentAvatar - don't send it here to avoid saving presigned URL
        system_prompt: formData.system_prompt,
        suggestion_prompts: suggestionPrompts,
        is_public: formData.is_public,
        portal_visibility: formData.portal_visibility,
        category: formData.is_public ? formData.category : null,
        tags: formData.is_public && formData.tags
          ? formData.tags.split(',').map((t: string) => t.trim()).filter(Boolean)
          : [],
        observability_config: observabilityConfig,
        allow_transfer: multiAgentConfig.allow_transfer,
        transfer_scope: multiAgentConfig.transfer_scope,
        human_contact_id: formData.human_contact_id || null,
        execution_backend: executionBackend,
        ...(Object.keys(agentMetadata).length > 0 && { agent_metadata: agentMetadata }),
      })

      toast.success('Agent updated successfully!')
      const newSlug = updateResponse?.data?.slug || agentName
      router.push(`/agents/${newSlug}/view`)
    } catch (error) {
      console.error('Failed to update agent:', error)
      toast.error('Failed to update agent')
    } finally {
      setSaving(false)
    }
  }

  const tabs = [
    { id: 'general' as Tab, label: 'General', icon: Info },
    { id: 'llm-models' as Tab, label: 'AI Model', icon: Sparkles },
    { id: 'context' as Tab, label: 'Skills', icon: FileText },
    { id: 'vision' as Tab, label: 'Vision', icon: Settings },
    { id: 'observability' as Tab, label: 'Observability', icon: Activity },
    { id: 'multi-agent' as Tab, label: 'Multi-Agent', icon: Wrench },
    { id: 'performance' as Tab, label: 'Performance', icon: Zap },
    { id: 'integrations' as Tab, label: 'Integrations', icon: Link },
    { id: 'advanced' as Tab, label: 'Advanced', icon: Settings },
    { id: 'landing-page' as Tab, label: 'Landing Page', icon: Globe },
    { id: 'email' as Tab, label: 'Email', icon: Mail },
  ]

  if (loading) {
    return (
      <div className="agent-workspace min-h-full px-4 py-4 md:px-8 md:py-6 xl:px-10">
        <div className="mx-auto flex min-h-[70vh] max-w-[90rem] items-center justify-center">
          <div className="dashboard-surface rounded-[2rem] px-10 py-12 text-center">
            <div className="mx-auto h-12 w-12 animate-spin rounded-full border-[3px] border-black/10 border-t-[#181818]"></div>
            <p className="mt-4 text-[14px] text-[#5b564e]">Loading agent details...</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="agent-workspace min-h-full px-4 py-4 md:px-8 md:py-6 xl:px-10">
      <div className="mx-auto max-w-[90rem]">
        {/* Header */}
        <div className="mb-6">
          <div className="dashboard-surface flex flex-col gap-4 rounded-[2rem] p-5 md:p-6 xl:flex-row xl:items-center xl:justify-between xl:p-7">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-3.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6e675d]">
                <Sparkles className="h-3 w-3 text-[#ff5f8f]" />
                Agent Editor
              </div>
              <h1 className="text-[1.8rem] font-semibold tracking-[-0.05em] text-[#171717] md:text-[2.65rem]">
                Edit <span className="highlight-mint">Agent</span>
              </h1>
              <p className="mt-2 text-[13px] text-[#5b564e] md:text-[15px]">
                Configure <span className="font-semibold text-gray-900">{formData.name}</span> settings
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => router.push(`/agents/${agentName}/view`)}
                className="rounded-full border border-black/10 bg-white/[0.72] px-5 py-3 text-[13px] font-medium text-[#171717] transition-colors hover:bg-white"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={saving || !formData.name}
                className="rounded-full bg-[#181818] px-5 py-3 text-[13px] font-medium text-[#f7f2e7] transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving ? (
                  <span className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    Saving...
                  </span>
                ) : (
                  'Save Changes'
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Modern Tabs */}
        <div className="dashboard-panel overflow-hidden rounded-[2rem]">
          <div className="border-b border-black/[0.08] bg-[#f1eadc]">
            <nav className="flex flex-wrap gap-1 p-2">
              {tabs.map((tab) => {
                const Icon = tab.icon
                const isActive = activeTab === tab.id
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-all rounded-lg ${
                      isActive
                        ? 'bg-[#181818] text-[#f7f2e7] shadow-[0_18px_40px_rgba(0,0,0,0.12)]'
                        : 'border border-black/10 bg-white/60 text-gray-600 hover:text-gray-900 hover:bg-white/80'
                    }`}
                  >
                    <Icon size={16} />
                    <span className="hidden sm:inline">{tab.label}</span>
                  </button>
                )
              })}
            </nav>
          </div>

          {/* Tab Content */}
          <div className="p-4 md:p-8">
            {activeTab === 'general' && (
              <GeneralTab
                formData={formData}
                setFormData={setFormData}
                isEdit={true}
                onAvatarUpload={handleAvatarUpload}
                onAvatarRemove={handleAvatarRemove}
                humanContacts={humanContacts}
              />
            )}
            {activeTab === 'llm-models' && (
              <LLMModelsTab agentName={agentName} />
            )}
            {activeTab === 'context' && (
              <ContextTab agentName={agentName} />
            )}
            {activeTab === 'vision' && (
              <VisionTab
                formData={formData}
                setFormData={setFormData}
                agentLlmConfigs={agentLlmConfigs}
                imageGenLlmConfigId={imageGenLlmConfigId}
                setImageGenLlmConfigId={setImageGenLlmConfigId}
              />
            )}
            {activeTab === 'observability' && (
              <ObservabilityTab 
                config={observabilityConfig} 
                setConfig={setObservabilityConfig} 
              />
            )}
            {activeTab === 'multi-agent' && (
              <MultiAgentTab 
                config={multiAgentConfig} 
                setConfig={setMultiAgentConfig}
                agentName={agentName}
              />
            )}
            {activeTab === 'performance' && (
              <PerformanceConfig
                config={performanceConfig}
                setConfig={setPerformanceConfig}
                agenticConfig={agenticConfig}
                setAgenticConfig={setAgenticConfig}
                executionBackend={executionBackend}
                setExecutionBackend={setExecutionBackend}
                hasServerlessExecution={hasServerlessExecution}
              />
            )}
            {activeTab === 'integrations' && (
              <IntegrationsTab
                agentId={agentId}
                agentName={formData.name}
                agentDescription={formData.description}
                config={integrationsConfig}
                setConfig={setIntegrationsConfig}
              />
            )}
            {activeTab === 'advanced' && (
              <AdvancedTab
                formData={formData}
                setFormData={setFormData}
                piiRedactionConfig={piiRedactionConfig}
                setPiiRedactionConfig={setPiiRedactionConfig}
              />
            )}
            {activeTab === 'landing-page' && (
              <div className="space-y-4 py-4">
                <div className="dashboard-surface rounded-[1.5rem] p-6 flex items-start gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary-100 mt-1">
                    <Globe className="h-5 w-5 text-primary-600" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 mb-1">Landing Page</h3>
                    <p className="text-sm text-gray-500 mb-4">
                      Hero image, tagline, description, gallery, video, SEO, and publish controls.
                    </p>
                    <a
                      href={`/agents/${agentName}/landing-page`}
                      className="inline-flex items-center gap-2 rounded-full bg-[#181818] px-4 py-2.5 text-sm font-medium text-white transition-transform hover:-translate-y-0.5"
                    >
                      <Globe className="h-4 w-4" />
                      Open editor
                    </a>
                  </div>
                </div>
                <div className="dashboard-surface rounded-[1.5rem] p-6 flex items-start gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#fff0d9] mt-1">
                    <DollarSign className="h-5 w-5 text-[#d9a441]" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 mb-1">Monetization</h3>
                    <p className="text-sm text-gray-500 mb-4">
                      Set pricing tiers (session, daily, weekly, monthly), trial messages, email subscription pricing, and revenue share.
                    </p>
                    {agentId ? (
                      <a
                        href={`/billing/agent-pricing/${agentId}?from=${agentName}`}
                        className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/[0.72] px-4 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:bg-white"
                      >
                        <DollarSign className="h-4 w-4" />
                        Configure pricing
                      </a>
                    ) : (
                      <span className="text-sm text-gray-400">Loading...</span>
                    )}
                  </div>
                </div>
                <div className="dashboard-surface rounded-[1.5rem] p-6 flex items-start gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-red-100 mt-1">
                    <Tag className="h-5 w-5 text-[#ff5f8f]" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 mb-1">Discount Codes</h3>
                    <p className="text-sm text-gray-500 mb-4">
                      Create percentage or flat-credit discount codes for subscribers.
                    </p>
                    <a
                      href={`/agents/${agentName}/discount-codes`}
                      className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/[0.72] px-4 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:bg-white"
                    >
                      <Tag className="h-4 w-4" />
                      Manage codes
                    </a>
                  </div>
                </div>
                <div className="dashboard-surface rounded-[1.5rem] p-6 flex items-start gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary-100 mt-1">
                    <Users className="h-5 w-5 text-primary-600" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 mb-1">Subscribers</h3>
                    <p className="text-sm text-gray-500 mb-4">
                      View everyone who has paid for access to this agent.
                    </p>
                    <a
                      href={`/agents/${agentName}/subscribers`}
                      className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/[0.72] px-4 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:bg-white"
                    >
                      <Users className="h-4 w-4" />
                      View subscribers
                    </a>
                  </div>
                </div>
              </div>
            )}
            {activeTab === 'email' && (
              <div className="space-y-6 py-4 max-w-2xl">
                <div>
                  <h2 className="text-base font-semibold text-gray-900 mb-1">Email <span className="highlight-pink">Template</span></h2>
                  <p className="text-sm text-gray-500">
                    Assign a reusable email template to this agent. When the agent sends emails or renders newsletters,
                    the selected template will be applied automatically.
                  </p>
                </div>

                {/* Currently assigned */}
                {assignedTemplate ? (
                  <div className="rounded-lg border border-green-200 bg-green-50 p-4 flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <Mail className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
                      <div>
                        <p className="font-medium text-gray-900 text-sm">{assignedTemplate.name}</p>
                        {assignedTemplate.description && (
                          <p className="text-xs text-gray-500 mt-0.5">{assignedTemplate.description}</p>
                        )}
                        <span className="mt-1 inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                          {assignedTemplate.template_type}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={handleRemoveTemplate}
                      disabled={emailTabSaving}
                      className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                      title="Remove template"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 italic">No email template assigned.</p>
                )}

                {/* Assign / change */}
                <div className="space-y-3">
                  <label className="block text-sm font-medium text-gray-700">
                    {assignedTemplate ? 'Change template' : 'Assign a template'}
                  </label>
                  {allTemplates.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-gray-300 p-5 text-center">
                      <Mail className="h-8 w-8 text-gray-300 mx-auto mb-2" />
                      <p className="text-sm text-gray-500 mb-3">No email templates found.</p>
                      <a
                        href="/email-templates"
                        className="inline-flex items-center gap-1.5 text-sm font-medium text-primary-600 hover:text-primary-700"
                      >
                        <ExternalLink size={14} />
                        Create a template
                      </a>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <select
                        value={selectedTemplateId}
                        onChange={e => setSelectedTemplateId(e.target.value)}
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                      >
                        <option value="">— select a template —</option>
                        {allTemplates.map(t => (
                          <option key={t.id} value={t.id}>
                            {t.name} ({t.template_type})
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={handleAssignTemplate}
                        disabled={!selectedTemplateId || emailTabSaving || selectedTemplateId === assignedTemplate?.id}
                        className="px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {emailTabSaving ? 'Saving…' : 'Assign'}
                      </button>
                    </div>
                  )}
                  <p className="text-xs text-gray-400">
                    Manage all templates in{' '}
                    <a href="/email-templates" className="text-primary-600 hover:underline inline-flex items-center gap-1">
                      Email Templates <ExternalLink size={11} />
                    </a>
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between border-t border-black/[0.08] bg-[#f1eadc] px-6 py-4 md:px-8">
            <div className="text-[13px] text-gray-600">
              Configure tools and MCP servers from the agent's dedicated pages
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => router.push(`/agents/${agentName}/view`)}
                className="rounded-full border border-black/10 bg-white/[0.72] px-6 py-2.5 text-[13px] font-medium text-[#171717] transition-colors hover:bg-white"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={saving || !formData.name}
                className="rounded-full bg-[#181818] px-6 py-2.5 text-[13px] font-medium text-[#f7f2e7] transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// General Tab Component
function GeneralTab({ formData, setFormData, isEdit, onAvatarUpload, onAvatarRemove, humanContacts }: any) {
  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-start gap-6 mb-6">
        <div className="flex-shrink-0">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Agent Avatar
          </label>
          <AvatarUpload
            currentAvatar={formData.avatar}
            onUpload={onAvatarUpload}
            onRemove={onAvatarRemove}
          />
        </div>
        <div className="flex-grow">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Agent Type
          </label>
          <select
            value={formData.agent_type}
            onChange={(e) => setFormData({ ...formData, agent_type: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            required
            disabled={isEdit}
          >
            <option value="LLM">LLM Agent (General Purpose)</option>
            <option value="RESEARCH">Research Agent</option>
            <option value="CODE">Code Agent</option>
            <option value="CLAUDE_CODE">Claude Code Agent</option>
          </select>
        </div>
      </div>

      {/* Human Escalation Settings */}
      <div className="border-t border-gray-200 pt-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Human Escalation (Optional)</h3>
        <p className="text-sm text-gray-600 mb-4">
          Link a human contact for escalation support when the agent needs help.
        </p>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Human Contact
          </label>
          <select
            value={formData.human_contact_id}
            onChange={(e) => setFormData({ ...formData, human_contact_id: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            <option value="">No human contact</option>
            {humanContacts?.map((contact: any) => (
              <option key={contact.id} value={contact.id}>
                {contact.name} {contact.email ? `(${contact.email})` : ''}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-gray-500">
            The agent can escalate to this person when it needs help
          </p>
        </div>
      </div>


      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Agent Name *
          </label>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            placeholder="my_assistant"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Description *
          </label>
          <input
            type="text"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            placeholder="A helpful AI assistant"
            required
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          System Prompt *
        </label>
        <textarea
          value={formData.system_prompt}
          onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          rows={6}
          placeholder="You are a helpful AI assistant with access to various tools and capabilities..."
          required
        />
      </div>

      {/* Portal Visibility */}
      <div className="border-t border-gray-200 pt-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-1">Portal Visibility</h3>
        <p className="text-sm text-gray-500 mb-4">Control how this agent appears on your white-label portal.</p>
        <select
          value={formData.portal_visibility}
          onChange={(e) => setFormData({ ...formData, portal_visibility: e.target.value })}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          <option value="hidden">Hidden — not shown on portal public pages</option>
          <option value="public">Public — visible to anyone on your portal</option>
          <option value="members_only">Members Only — visible to logged-in portal users</option>
        </select>
      </div>

      {/* Marketplace Settings */}
      <div className="border-t border-gray-200 pt-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Marketplace Settings</h3>
        
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="is_public"
              checked={formData.is_public}
              onChange={(e) => setFormData({ ...formData, is_public: e.target.checked })}
              className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            />
            <label htmlFor="is_public" className="text-sm font-medium text-gray-700">
              Make this agent public in the marketplace
            </label>
          </div>

          {formData.is_public && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Category
                </label>
                <select
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                >
                  <option value="">Select a category</option>
                  <option value="Productivity">Productivity</option>
                  <option value="Research">Research</option>
                  <option value="Development">Development</option>
                  <option value="Writing">Writing</option>
                  <option value="Data Analysis">Data Analysis</option>
                  <option value="Customer Support">Customer Support</option>
                  <option value="Education">Education</option>
                  <option value="Entertainment">Entertainment</option>
                  <option value="Other">Other</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Tags (comma-separated)
                </label>
                <input
                  type="text"
                  value={formData.tags}
                  onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder="e.g., automation, productivity, research"
                />
                <p className="mt-1 text-sm text-gray-500">
                  Add tags to help users discover your agent
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Suggestion Prompts (Optional)
        </label>
        <p className="text-sm text-gray-600 mb-3">
          Add suggested prompts as a JSON array. Each prompt can be a string or an object with title, description, prompt, and icon.
        </p>
        <textarea
          value={formData.suggestion_prompts}
          onChange={(e) => setFormData({ ...formData, suggestion_prompts: e.target.value })}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent font-mono text-sm"
          rows={8}
          placeholder={`[\n  "Simple text prompt",\n  {\n    "title": "Rich Prompt",\n    "description": "A prompt with details",\n    "prompt": "Tell me about...",\n    "icon": "💡"\n  }\n]`}
        />
        <div className="mt-2 bg-red-50 border border-primary-200 rounded-lg p-3">
          <p className="text-sm font-medium text-primary-900 mb-2">📝 Format Examples:</p>
          <div className="text-xs text-primary-800 space-y-2">
            <div>
              <strong>Simple strings:</strong>
              <pre className="mt-1 bg-white p-2 rounded border border-primary-300 overflow-x-auto">
{`["What can you help me with?", "Explain your capabilities"]`}
              </pre>
            </div>
            <div>
              <strong>Rich objects:</strong>
              <pre className="mt-1 bg-white p-2 rounded border border-primary-300 overflow-x-auto">
{`[
  {
    "title": "Get Started",
    "description": "Learn what I can do",
    "prompt": "What are your main capabilities?",
    "icon": "🚀"
  }
]`}
              </pre>
            </div>
          </div>
        </div>
      </div>

    </div>
  )
}

// Skills Tab Component
function ContextTab({ agentName }: { agentName: string }) {
  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Skills
        </h3>
        <p className="text-sm text-gray-600 mb-4">
          Upload documents to provide permanent context to your agent. These files will be automatically included in the agent's system prompt.
        </p>
      </div>

      <div className="bg-red-50 border border-primary-200 rounded-lg p-4 mb-6">
        <h4 className="text-sm font-medium text-primary-900 mb-2">💡 Use Cases</h4>
        <ul className="text-sm text-primary-800 space-y-1 list-disc list-inside">
          <li>API documentation and technical specifications</li>
          <li>Code style guides and best practices</li>
          <li>Domain-specific knowledge and research papers</li>
          <li>Brand guidelines and writing style guides</li>
          <li>Reference implementations and examples</li>
        </ul>
      </div>

      <ContextFilesUpload agentName={agentName} />
    </div>
  )
}

// Observability Tab Component
function ObservabilityTab({ config, setConfig }: any) {
  const langfuseUrl = config.langfuse_host || process.env.NEXT_PUBLIC_LANGFUSE_URL || 'http://localhost:3001'
  
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Langfuse Observability
        </h3>
        <p className="text-sm text-gray-600 mb-4">
          Configure tracing and monitoring for your agent using Langfuse. Track LLM calls, tool usage, and RAG queries.
        </p>
      </div>

      <div className="bg-red-50 border border-primary-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-primary-900 mb-2">📊 What is Langfuse?</h4>
        <p className="text-sm text-primary-800 mb-2">
          Langfuse is an open-source LLM engineering platform that provides:
        </p>
        <ul className="text-sm text-primary-800 space-y-1 list-disc list-inside">
          <li>Detailed traces of agent execution and LLM calls</li>
          <li>Performance metrics and cost tracking</li>
          <li>Tool and RAG query monitoring</li>
          <li>Session-based conversation tracking</li>
        </ul>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200">
          <div>
            <label className="text-sm font-medium text-gray-900">
              Enable Langfuse Tracing
            </label>
            <p className="text-xs text-gray-600 mt-1">
              Turn on observability for this agent
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={config.langfuse_enabled}
              onChange={(e) => setConfig({ ...config, langfuse_enabled: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
          </label>
        </div>

        {config.langfuse_enabled && (
          <>
            <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Sample Rate: {(config.sample_rate * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={config.sample_rate}
                onChange={(e) => setConfig({ ...config, sample_rate: parseFloat(e.target.value) })}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <p className="text-xs text-gray-600 mt-2">
                Percentage of requests to trace (1.0 = 100%, 0.1 = 10%)
              </p>
            </div>

            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div>
                <label className="text-sm font-medium text-gray-900">
                  Trace Tool Calls
                </label>
                <p className="text-xs text-gray-600 mt-1">
                  Track all tool executions as spans
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.trace_tools}
                  onChange={(e) => setConfig({ ...config, trace_tools: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
              </label>
            </div>

            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div>
                <label className="text-sm font-medium text-gray-900">
                  Trace RAG Queries
                </label>
                <p className="text-xs text-gray-600 mt-1">
                  Track knowledge base queries and retrievals
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.trace_rag}
                  onChange={(e) => setConfig({ ...config, trace_rag: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
              </label>
            </div>

            <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-4">
              <div>
                <h4 className="text-sm font-semibold text-gray-900 mb-1">Langfuse Credentials (Optional)</h4>
                <p className="text-xs text-gray-600 mb-3">
                  Configure per-agent Langfuse credentials to use your own Langfuse instance. Leave blank to use the platform-wide Langfuse settings.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Langfuse Host URL
                </label>
                <input
                  type="url"
                  value={config.langfuse_host}
                  onChange={(e) => setConfig({ ...config, langfuse_host: e.target.value })}
                  placeholder="https://cloud.langfuse.com"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Public Key
                </label>
                <input
                  type="text"
                  value={config.langfuse_public_key}
                  onChange={(e) => setConfig({ ...config, langfuse_public_key: e.target.value })}
                  placeholder="pk-lf-..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Secret Key
                </label>
                <input
                  type="password"
                  value={config.langfuse_secret_key}
                  onChange={(e) => setConfig({ ...config, langfuse_secret_key: e.target.value })}
                  placeholder="sk-lf-..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
              </div>
            </div>

            <div className="bg-red-50 border border-primary-200 rounded-lg p-4">
              <h4 className="text-sm font-medium text-primary-900 mb-2">View Traces</h4>
              <p className="text-sm text-primary-800 mb-3">
                Access your Langfuse dashboard to view traces and analytics:
              </p>
              <a
                href={langfuseUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors text-sm"
              >
                Open Langfuse Dashboard
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>
          </>
        )}
      </div>

      <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-orange-900 mb-2">💡 Best Practices</h4>
        <ul className="text-sm text-orange-800 space-y-1 list-disc list-inside">
          <li>Use 100% sampling during development and testing</li>
          <li>Reduce sample rate in production to manage costs</li>
          <li>Enable tool and RAG tracing for debugging</li>
          <li>Review traces regularly to optimize performance</li>
        </ul>
      </div>
    </div>
  )
}

// Image models that can be assigned for image generation
const IMAGE_GENERATION_MODELS = new Set([
  'gpt-image-1', 'gpt-image-2', 'dall-e-3', 'dall-e-2',
  'imagen-3.0-generate-002', 'imagen-3.0-fast-generate-001',
  'grok-2-image',
])

// Vision Tab Component
function VisionTab({ formData, agentLlmConfigs, imageGenLlmConfigId, setImageGenLlmConfigId }: any) {
  // Vision models by provider
  const VISION_MODELS = {
    OPENAI: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4-vision-preview'],
    anthropic: ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
    google: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro-vision']
  }

  const supportsVision = (provider: string) => {
    return ['OPENAI', 'anthropic', 'google'].includes(provider)
  }

  const isVisionModel = (provider: string, model: string) => {
    const visionModels = VISION_MODELS[provider as keyof typeof VISION_MODELS] || []
    return visionModels.includes(model)
  }

  // Filter LLM configs to only those with image generation models
  const imageGenConfigs = (agentLlmConfigs || []).filter(
    (cfg: AgentLLMConfig) => IMAGE_GENERATION_MODELS.has(cfg.model_name)
  )

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Vision & Image Generation
        </h3>
        <p className="text-sm text-gray-600 mb-4">
          Configure image analysis (vision) and image generation capabilities for this agent.
        </p>
      </div>

      {/* ---- Image Generation section ---- */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
        <h4 className="text-sm font-semibold text-gray-900 mb-1">Image Generation Model</h4>
        <p className="text-xs text-gray-500 mb-4">
          Select which LLM config the image generation tool should use. Only configs with an image
          model (gpt-image-1, gpt-image-2, dall-e-3, dall-e-2, Imagen, grok-2-image) are shown.
        </p>

        {imageGenConfigs.length === 0 ? (
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
            <p className="text-sm text-orange-800">
              No image generation models found. Add an LLM config with an image model (e.g.
              gpt-image-1, gpt-image-2, dall-e-3) in the <strong>AI Model</strong> tab, then come back here to
              assign it.
            </p>
          </div>
        ) : (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">
              Image Generation Config
            </label>
            <select
              value={imageGenLlmConfigId}
              onChange={(e) => setImageGenLlmConfigId(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white"
            >
              <option value="">— None (image generation disabled) —</option>
              {imageGenConfigs.map((cfg: AgentLLMConfig) => (
                <option key={cfg.id} value={cfg.id}>
                  {cfg.name} ({cfg.model_name})
                </option>
              ))}
            </select>
            {imageGenLlmConfigId && (
              <p className="text-xs text-emerald-700 mt-1.5">
                Image generation tool will use this config. Click <strong>Save Changes</strong> to apply.
              </p>
            )}
          </div>
        )}
      </div>

      {/* ---- Vision (image analysis) section ---- */}
      {!supportsVision(formData.provider) ? (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
          <h4 className="text-sm font-medium text-orange-900 mb-2">Vision Not Supported</h4>
          <p className="text-sm text-orange-800">
            The selected provider ({formData.provider}) does not support vision capabilities.
            Please switch to OpenAI, Anthropic Claude, or Google Gemini to enable vision features.
          </p>
        </div>
      ) : (
        <>
          <div className="bg-red-50 border border-primary-200 rounded-lg p-4">
            <h4 className="text-sm font-medium text-primary-900 mb-2">About Vision</h4>
            <p className="text-sm text-primary-800 mb-2">
              Vision-enabled agents can:
            </p>
            <ul className="text-sm text-primary-800 space-y-1 list-disc list-inside">
              <li>Analyze images attached to chat messages</li>
              <li>Extract text from images (OCR)</li>
              <li>Describe visual content and scenes</li>
              <li>Answer questions about images</li>
              <li>Identify objects, people, and activities</li>
            </ul>
          </div>

          <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
            <h4 className="text-sm font-medium text-emerald-900 mb-2">Current Model Supports Vision</h4>
            <p className="text-sm text-emerald-800">
              Your selected model <strong>{formData.model_name}</strong> {isVisionModel(formData.provider, formData.model_name) ? 'supports' : 'may support'} vision capabilities.
              {!isVisionModel(formData.provider, formData.model_name) && ' Please verify with your provider.'}
            </p>
          </div>

          <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
            <h4 className="text-sm font-medium text-orange-900 mb-2">Note</h4>
            <p className="text-sm text-orange-800">
              Vision configuration is stored in your agent's LLM config. The backend automatically handles vision API calls when images are attached to messages.
              No additional configuration is needed — vision works automatically with compatible models!
            </p>
          </div>

          <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
            <h4 className="text-sm font-medium text-purple-900 mb-2">Supported Providers</h4>
            <div className="space-y-2 text-sm text-purple-800">
              <div>
                <strong>OpenAI:</strong> gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-4-vision-preview
              </div>
              <div>
                <strong>Anthropic:</strong> All Claude 3+ models (Opus, Sonnet, Haiku)
              </div>
              <div>
                <strong>Google:</strong> gemini-1.5-pro, gemini-1.5-flash, gemini-pro-vision
              </div>
            </div>
          </div>

          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <h4 className="text-sm font-medium text-gray-900 mb-2">How to Use</h4>
            <ol className="text-sm text-gray-800 space-y-2 list-decimal list-inside">
              <li>Ensure your agent uses a vision-capable model (see supported models above)</li>
              <li>In chat, attach images using the file upload button</li>
              <li>Ask questions about the images in your message</li>
              <li>The agent will automatically analyze the images and respond</li>
            </ol>
          </div>

          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <h4 className="text-sm font-medium text-red-900 mb-2">Important Notes</h4>
            <ul className="text-sm text-red-800 space-y-1 list-disc list-inside">
              <li>Vision API calls are more expensive than text-only calls</li>
              <li>Image tokens count towards your total token limit</li>
              <li>Large images may require more tokens to process</li>
              <li>Maximum file size: 10MB per image</li>
              <li>Supported formats: JPEG, PNG, GIF, WebP</li>
            </ul>
          </div>
        </>
      )}
    </div>
  )
}

// LLM Models Tab Component
function LLMModelsTab({ agentName }: { agentName: string }) {
  const { 
    configs, 
    isLoading, 
    create: createConfig, 
    update: updateConfig, 
    delete: deleteConfig, 
    setDefault: setDefaultConfig,
  } = useLLMConfigManager(agentName)
  const [showForm, setShowForm] = useState(false)
  const [editingConfig, setEditingConfig] = useState<AgentLLMConfig | undefined>()
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleAdd = () => {
    setEditingConfig(undefined)
    setShowForm(true)
  }

  const handleEdit = (config: AgentLLMConfig) => {
    setEditingConfig(config)
    setShowForm(true)
  }

  const handleCancel = () => {
    setShowForm(false)
    setEditingConfig(undefined)
  }

  const handleSubmit = async (data: AgentLLMConfigCreate | AgentLLMConfigUpdate) => {
    setIsSubmitting(true)
    try {
      if (editingConfig) {
        await updateConfig(editingConfig.id, data as AgentLLMConfigUpdate)
        toast.success('Configuration updated successfully')
      } else {
        await createConfig(data as AgentLLMConfigCreate)
        toast.success('Configuration created successfully')
      }
      setShowForm(false)
      setEditingConfig(undefined)
    } catch (error: any) {
      toast.error(error.message || 'Failed to save configuration')
    } finally {
      setIsSubmitting(false)
    }
  }
  const handleDelete = async (configId: string) => {
    if (!confirm('Are you sure you want to delete this configuration?')) { 
      return
    }
    try {
      await deleteConfig(configId)
      toast.success('Configuration deleted successfully')
    } catch (error: any) {
      toast.error(error.message || 'Failed to delete configuration')
    }
  }
  const handleSetDefault = async (configId: string) => {
    try {
      await setDefaultConfig(configId)
      toast.success('Default configuration set successfully')
    } catch (error: any) {
      toast.error(error.message || 'Failed to set default configuration')
    }
  }
  const handleToggleEnabled = async (configId: string, enabled: boolean) => {
    try {
      await updateConfig(configId, { enabled })
      toast.success('Configuration enabled/disabled successfully')
    } catch (error: any) {
      toast.error(error.message || 'Failed to enable/disable configuration')
    }
  }
  return (
    <div className="space-y-6 max-w-4xl">
      {!showForm && (
        <>
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              LLM Model Configurations
            </h3>
            <p className="text-sm text-gray-600 mb-4">
              Configure multiple LLM models for your agent. You can switch between different models or use them for specific tasks.
            </p>
          </div>
 
 
          <div className="bg-red-50 border border-primary-200 rounded-lg p-4">
            <h4 className="text-sm font-medium text-primary-900 mb-2">💡 Why Multiple Models?</h4>
            <ul className="text-sm text-primary-800 space-y-1 list-disc list-inside">
              <li>Use different models for different tasks (e.g., GPT-4 for complex reasoning, GPT-3.5 for simple queries)</li>
              <li>Fallback to alternative models if primary model fails</li>
              <li>Cost optimization by using cheaper models when appropriate</li>
              <li>A/B testing different models for performance comparison</li>
              <li>Provider redundancy for better reliability</li>
            </ul>
          </div>
        </>
      )}
 
 
      {showForm ? (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900">
              {editingConfig ? 'Edit Configuration' : 'Add Configuration'}
            </h2>
            <button
              onClick={handleCancel}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-600" />
            </button>
          </div>
          <LLMConfigForm
            config={editingConfig}
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            isSubmitting={isSubmitting}
          />
        </div>
      ) : (
        <LLMConfigList
          configs={configs}
          onAdd={handleAdd}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onSetDefault={handleSetDefault}
          onToggleEnabled={handleToggleEnabled}
          isLoading={isLoading}
        />
      )}
    </div>
  )
 }
 
 

// Multi-Agent Tab Component
function MultiAgentTab({ config, setConfig, agentName }: any) {
  const router = useRouter()
  
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Multi-Agent Configuration
        </h3>
        <p className="text-sm text-gray-600 mb-4">
          Configure how this agent can transfer control to other agents in a multi-agent system.
        </p>
      </div>

      <div className="bg-red-50 border border-primary-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-primary-900 mb-2">🤝 What is Multi-Agent?</h4>
        <p className="text-sm text-primary-800 mb-2">
          Multi-agent systems allow you to:
        </p>
        <ul className="text-sm text-primary-800 space-y-1 list-disc list-inside">
          <li>Break down complex tasks into specialized sub-agents</li>
          <li>Enable dynamic routing based on request type</li>
          <li>Create hierarchical agent systems</li>
          <li>Reuse agents across different parent agents</li>
        </ul>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200">
          <div>
            <label className="text-sm font-medium text-gray-900">
              Enable Agent Transfer
            </label>
            <p className="text-xs text-gray-600 mt-1">
              Allow this agent to transfer control to other agents
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={config.allow_transfer}
              onChange={(e) => setConfig({ ...config, allow_transfer: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
          </label>
        </div>

        {config.allow_transfer && (
          <>
            <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Transfer Scope
              </label>
              <select
                value={config.transfer_scope}
                onChange={(e) => setConfig({ ...config, transfer_scope: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              >
                <option value="sub_agents">Sub-Agents Only - Can only transfer to linked sub-agents</option>
                <option value="all">All Agents - Can transfer to any agent in the system</option>
                <option value="parent">Parent Only - Can only transfer back to parent agent</option>
              </select>
              <p className="text-xs text-gray-600 mt-2">
                {config.transfer_scope === 'sub_agents' && 'Most common: Agent can only delegate to its configured sub-agents'}
                {config.transfer_scope === 'all' && 'Flexible: Agent can transfer to any agent (use with caution)'}
                {config.transfer_scope === 'parent' && 'Restrictive: Agent can only escalate back to its parent'}
              </p>
            </div>

            <div className="bg-red-50 border border-primary-200 rounded-lg p-4">
              <h4 className="text-sm font-medium text-primary-900 mb-2">📋 How It Works</h4>
              <ol className="text-sm text-primary-800 space-y-2 list-decimal list-inside">
                <li>Link sub-agents in the <strong>Sub-Agents</strong> tab</li>
                <li>Configure your agent's system prompt to include transfer instructions</li>
                <li>The agent will use the <code className="bg-white px-1 rounded">transfer_to_agent</code> function</li>
                <li>Control is passed to the specified agent</li>
              </ol>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => router.push(`/agents/${agentName}/sub-agents`)}
                className="flex-1 px-4 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-medium"
              >
                Manage Sub-Agents →
              </button>
              <button
                onClick={() => window.open('/docs/MULTI_AGENT_UI_GUIDE.md', '_blank')}
                className="px-4 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors font-medium"
              >
                📖 View Guide
              </button>
            </div>
          </>
        )}

        {!config.allow_transfer && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <p className="text-sm text-gray-600">
              Enable agent transfer to use multi-agent capabilities. This allows your agent to delegate tasks to specialized sub-agents.
            </p>
          </div>
        )}
      </div>

      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-purple-900 mb-2">🎯 Example Use Case</h4>
        <p className="text-sm text-purple-800 mb-2">
          <strong>Customer Support System:</strong>
        </p>
        <div className="text-sm text-purple-800 space-y-1">
          <div>• <strong>Help Desk Coordinator</strong> (this agent) - Routes requests</div>
          <div className="ml-4">↳ <strong>Billing Agent</strong> (sub-agent) - Handles payment issues</div>
          <div className="ml-4">↳ <strong>Technical Support</strong> (sub-agent) - Handles bugs</div>
          <div className="ml-4">↳ <strong>Account Management</strong> (sub-agent) - Handles account changes</div>
        </div>
      </div>

      <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-orange-900 mb-2">💡 Best Practices</h4>
        <ul className="text-sm text-orange-800 space-y-1 list-disc list-inside">
          <li>Use <strong>sub_agents</strong> scope for contained, predictable systems</li>
          <li>Write clear transfer instructions in the system prompt</li>
          <li>Give sub-agents descriptive names and descriptions</li>
          <li>Test transfer scenarios thoroughly</li>
          <li>Avoid circular dependencies between agents</li>
        </ul>
      </div>
    </div>
  )
}

const ALL_PII_PATTERNS = ['email', 'phone', 'ssn', 'credit_card', 'ip_address']

// Advanced Tab Component
function AdvancedTab({ formData, setFormData, piiRedactionConfig, setPiiRedactionConfig }: any) {
  const togglePattern = (pattern: string) => {
    const current: string[] = piiRedactionConfig.patterns
    const updated = current.includes(pattern)
      ? current.filter((p: string) => p !== pattern)
      : [...current, pattern]
    setPiiRedactionConfig({ ...piiRedactionConfig, patterns: updated })
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          Advanced LLM Settings
        </h3>
        <p className="text-sm text-gray-600 mb-4">
          Fine-tune your agent's behavior with advanced parameters.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Temperature
          </label>
          <input
            type="number"
            step="0.1"
            min="0"
            max="2"
            value={formData.temperature}
            onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
          <p className="mt-1 text-xs text-gray-500">
            Controls randomness (0 = focused, 2 = creative)
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Max Tokens
          </label>
          <input
            type="number"
            step="256"
            min="256"
            max="32768"
            value={formData.max_tokens}
            onChange={(e) => setFormData({ ...formData, max_tokens: parseInt(e.target.value) })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
          <p className="mt-1 text-xs text-gray-500">
            Maximum response length
          </p>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Top P
        </label>
        <input
          type="number"
          step="0.1"
          min="0"
          max="1"
          value={formData.top_p}
          onChange={(e) => setFormData({ ...formData, top_p: parseFloat(e.target.value) })}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
        <p className="mt-1 text-xs text-gray-500">
          Nucleus sampling threshold (0.1 = focused, 1.0 = diverse)
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Extra Headers (Optional)
        </label>
        <textarea
          value={formData.extra_headers}
          onChange={(e) => setFormData({ ...formData, extra_headers: e.target.value })}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent font-mono text-sm"
          rows={6}
          placeholder='{\n  "anthropic-beta": "max-tokens-3-5-sonnet-2024-07-15"\n}'
        />
        <p className="mt-1 text-xs text-gray-500">
          JSON object for custom API headers (e.g., for Claude extended context). Leave empty if not needed.
        </p>
      </div>

      <div className="bg-red-50 border border-primary-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-primary-900 mb-2">💡 Claude Extended Context</h4>
        <p className="text-sm text-primary-800 mb-2">
          To enable Claude 4.5 Sonnet's 1M token context window, add:
        </p>
        <pre className="text-xs bg-white p-2 rounded border border-primary-300 overflow-x-auto">
{`{
  "anthropic-beta": "max-tokens-3-5-sonnet-2024-07-15"
}`}
        </pre>
        <p className="text-sm text-primary-800 mt-2">
          Then increase Max Tokens to 50000 or higher for output.
        </p>
      </div>

      <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-orange-900 mb-2">⚠️ Advanced Settings</h4>
        <p className="text-sm text-orange-800">
          These settings can significantly affect your agent's behavior. The default values work well for most use cases.
          Only modify if you understand the implications.
        </p>
      </div>

      {/* Privacy & PII Redaction */}
      <div className="border border-gray-200 rounded-lg p-5 space-y-4">
        <div>
          <h3 className="text-base font-semibold text-gray-900">Privacy & PII Redaction</h3>
          <p className="text-xs text-gray-500 mt-1">
            Control how personal data is handled when tools return results to the agent.
          </p>
        </div>

        <label className="flex items-start gap-3 cursor-pointer">
          <div className="relative mt-0.5">
            <input
              type="checkbox"
              className="sr-only"
              checked={piiRedactionConfig.redact_for_llm}
              onChange={(e) =>
                setPiiRedactionConfig({ ...piiRedactionConfig, redact_for_llm: e.target.checked })
              }
            />
            <div
              className={`w-10 h-6 rounded-full transition-colors ${
                piiRedactionConfig.redact_for_llm ? 'bg-primary-600' : 'bg-gray-300'
              }`}
            />
            <div
              className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                piiRedactionConfig.redact_for_llm ? 'translate-x-4' : ''
              }`}
            />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">Redact PII from LLM</p>
            <p className="text-xs text-gray-500">
              Replace personal data in tool results with tokens (e.g. [EMAIL_1]) before the LLM
              sees them. Original values are restored in the response shown to users.
            </p>
          </div>
        </label>

        <label className="flex items-start gap-3 cursor-pointer">
          <div className="relative mt-0.5">
            <input
              type="checkbox"
              className="sr-only"
              checked={piiRedactionConfig.redact_for_response}
              onChange={(e) =>
                setPiiRedactionConfig({ ...piiRedactionConfig, redact_for_response: e.target.checked })
              }
            />
            <div
              className={`w-10 h-6 rounded-full transition-colors ${
                piiRedactionConfig.redact_for_response ? 'bg-primary-600' : 'bg-gray-300'
              }`}
            />
            <div
              className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                piiRedactionConfig.redact_for_response ? 'translate-x-4' : ''
              }`}
            />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">Redact PII from agent response</p>
            <p className="text-xs text-gray-500">
              Mask personal data in the response shown to users as well — users never see raw PII.
            </p>
          </div>
        </label>

        {(piiRedactionConfig.redact_for_llm || piiRedactionConfig.redact_for_response) && (
          <div>
            <p className="text-xs font-medium text-gray-700 mb-2">Patterns to detect:</p>
            <div className="flex flex-wrap gap-2">
              {ALL_PII_PATTERNS.map((p) => (
                <label key={p} className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={piiRedactionConfig.patterns.includes(p)}
                    onChange={() => togglePattern(p)}
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-xs text-gray-700 capitalize">{p.replace('_', ' ')}</span>
                </label>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
