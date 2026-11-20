'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import toast from 'react-hot-toast'
import { Copy, AlertTriangle, CheckCircle2, Cpu } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

interface CloneFormData {
  new_name: string
  new_api_key: string
  clone_tools: boolean
  clone_knowledge_bases: boolean
  clone_sub_agents: boolean
  clone_workflows: boolean
}

interface LLMConfig {
  id: string
  name: string
  provider: string
  model_name: string
  is_default: boolean
  enabled: boolean
}

function CloneOptionToggle({
  id,
  label,
  description,
  checked,
  onChange,
}: {
  id: string
  label: string
  description: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-lg border border-line p-3.5">
      <div className="flex-grow">
        <label htmlFor={id} className="block text-sm font-medium text-ink">
          {label}
        </label>
        <p className="mt-0.5 text-sm text-ink-mute">{description}</p>
      </div>
      <button
        type="button"
        id={id}
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
          checked ? 'bg-ink' : 'bg-line'
        }`}
      >
        <span
          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform motion-reduce:transition-none ${
            checked ? 'translate-x-4.5' : 'translate-x-0.5'
          }`}
        />
      </button>
    </div>
  )
}

export default function CloneAgentPage() {
  const router = useRouter()
  const params = useParams()
  const agentName = params.agentName as string

  const [formData, setFormData] = useState<CloneFormData>({
    new_name: '',
    new_api_key: '',
    clone_tools: true,
    clone_knowledge_bases: false,
    clone_sub_agents: false,
    clone_workflows: true,
  })

  const [cloning, setCloning] = useState(false)
  const [success, setSuccess] = useState(false)
  const [warnings, setWarnings] = useState<string[]>([])
  const [llmConfigs, setLlmConfigs] = useState<LLMConfig[]>([])
  const [loadingConfigs, setLoadingConfigs] = useState(true)

  // Fetch LLM configs when page loads
  useEffect(() => {
    const fetchLLMConfigs = async () => {
      if (!agentName) return

      try {
        const configs = await apiClient.getAgentLLMConfigs(agentName)
        setLlmConfigs(configs)
      } catch (error) {
        console.error('Failed to fetch LLM configs:', error)
      } finally {
        setLoadingConfigs(false)
      }
    }

    fetchLLMConfigs()
  }, [agentName])

  useEffect(() => {
    // Set default name as original + " (Copy)"
    if (agentName) {
      setFormData(prev => ({
        ...prev,
        new_name: `${decodeURIComponent(agentName)} (Copy)`
      }))
    }
  }, [agentName])

  // Get the default LLM config to show which API key is needed
  const defaultConfig = llmConfigs.find(c => c.is_default) || llmConfigs[0]

  const handleSubmit = async () => {
    if (!formData.new_name.trim()) {
      toast.error('Please enter a name for the cloned agent')
      return
    }

    setCloning(true)
    setSuccess(false)
    setWarnings([])

    try {
      const data = await apiClient.cloneAgent(agentName, formData)

      if (data.success) {
        setSuccess(true)
        if (data.data.warnings) {
          setWarnings(data.data.warnings)
        }
        toast.success('Agent cloned successfully!')
        
        // Redirect to the cloned agent after 2 seconds
        setTimeout(() => {
          router.push(`/agents/${data.data.slug}/edit`)
        }, 2000)
      } else {
        toast.error(data.message || 'Failed to clone agent')
      }
    } catch (error: any) {
      console.error('Failed to clone agent:', error)
      // Handle both middleware errors (message) and endpoint errors (detail)
      const errorMessage = error.response?.data?.message
        || error.response?.data?.detail
        || error.message
        || 'Failed to clone agent'
      toast.error(errorMessage)
    } finally {
      setCloning(false)
    }
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Clone Agent"
      description={`Create a copy of "${decodeURIComponent(agentName)}" with customizable settings.`}
      icon={Copy}
      backHref={`/agents/${encodeURIComponent(agentName)}/view`}
      backLabel="Back to Agent"
      actions={
        <>
          <button
            onClick={() => router.back()}
            disabled={cloning || success}
            className="px-4 py-2 border border-taupe rounded-lg text-sm font-medium text-ink-soft hover:bg-sand transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={cloning || success || !formData.new_name}
            className="flex items-center gap-2 px-4 py-2 bg-ink text-white rounded-lg text-sm font-medium hover:from-danger hover:to-danger transition-[color,background-color,border-color,box-shadow,opacity,transform] disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            {cloning ? (
              <>
                <div className="motion-safe:animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                Cloning...
              </>
            ) : (
              <>
                <Copy size={16} />
                Clone Agent
              </>
            )}
          </button>
        </>
      }
    >
      <div className="space-y-6 max-w-3xl">
        <AgentPagePanel className="p-5 md:p-6 space-y-6">
          {/* Agent Name */}
          <div>
            <label className="block text-sm font-medium text-ink mb-2">
              New Agent Name *
            </label>
            <input
              type="text"
              value={formData.new_name}
              onChange={(e) => setFormData({ ...formData, new_name: e.target.value })}
              className="w-full px-4 py-2 border border-line rounded-xl focus:ring-2 focus:ring-ink focus:border-transparent transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-200"
              placeholder="Enter new agent name"
              required
            />
            <p className="mt-1 text-sm text-ink-mute">
              A unique name for your cloned agent
            </p>
          </div>

          {/* API Key */}
          <div>
            <label className="block text-sm font-medium text-ink mb-2">
              New API Key (Optional)
            </label>

            {/* Show LLM Config Info */}
            {loadingConfigs ? (
              <div className="mb-3 p-3 bg-paper rounded-lg border border-sand-deep">
                <div className="motion-safe:animate-pulse flex items-center gap-2">
                  <div className="h-4 w-4 bg-line rounded"></div>
                  <div className="h-4 w-32 bg-line rounded"></div>
                </div>
              </div>
            ) : defaultConfig ? (
              <div className="mb-3 p-3 bg-paper rounded-lg border border-sand-deep">
                <div className="flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-bark" />
                  <span className="text-sm text-ink-soft">
                    This agent uses <span className="font-semibold text-ink">{defaultConfig.provider}</span> provider with model <span className="font-semibold text-ink">{defaultConfig.model_name}</span>
                  </span>
                </div>
                {llmConfigs.length > 1 && (
                  <p className="text-xs text-bark mt-1 ml-6">
                    + {llmConfigs.length - 1} more LLM config(s) that will need API keys configured separately
                  </p>
                )}
              </div>
            ) : (
              <div className="mb-3 p-3 bg-sand-deep rounded-lg border border-honey">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-warn" />
                  <span className="text-sm text-gold">
                    No LLM configuration found for this agent
                  </span>
                </div>
              </div>
            )}

            <input
              type="password"
              value={formData.new_api_key}
              onChange={(e) => setFormData({ ...formData, new_api_key: e.target.value })}
              className="w-full px-4 py-2 border border-line rounded-xl focus:ring-2 focus:ring-ink focus:border-transparent transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-200"
              placeholder={defaultConfig ? `Enter your ${defaultConfig.provider} API key` : "Leave empty to configure later"}
            />
            <p className="mt-1 text-sm text-ink-mute">
              {defaultConfig
                ? `Provide your ${defaultConfig.provider} API key to enable the cloned agent immediately`
                : "Configure LLM settings after cloning"
              }
            </p>
          </div>
        </AgentPagePanel>

        {/* Clone Options */}
        <AgentPagePanel className="p-5 md:p-6">
          <h3 className="text-sm font-semibold text-ink mb-4">Clone Options</h3>
          <div className="space-y-3">
            <CloneOptionToggle
              id="clone_tools"
              label="Clone Tool Configurations"
              description="Copy all tool settings and configurations"
              checked={formData.clone_tools}
              onChange={(checked) => setFormData({ ...formData, clone_tools: checked })}
            />
            <CloneOptionToggle
              id="clone_knowledge_bases"
              label="Clone Knowledge Base Links"
              description="Link same knowledge bases (OAuth sources need re-auth)"
              checked={formData.clone_knowledge_bases}
              onChange={(checked) => setFormData({ ...formData, clone_knowledge_bases: checked })}
            />
            <CloneOptionToggle
              id="clone_sub_agents"
              label="Clone Sub-agent Relationships"
              description="Copy all sub-agent connections and configs"
              checked={formData.clone_sub_agents}
              onChange={(checked) => setFormData({ ...formData, clone_sub_agents: checked })}
            />
            <CloneOptionToggle
              id="clone_workflows"
              label="Clone Workflow Configurations"
              description="Copy ADK workflow settings if enabled"
              checked={formData.clone_workflows}
              onChange={(checked) => setFormData({ ...formData, clone_workflows: checked })}
            />
          </div>
        </AgentPagePanel>

        {/* Important Notes */}
        <div className="bg-sand-deep border border-honey rounded-lg p-4">
          <div className="flex">
            <AlertTriangle className="h-5 w-5 text-warn mr-3 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-medium text-gold mb-2">Important Notes</h4>
              <ul className="list-disc list-inside space-y-1 text-sm text-gold">
                <li>If you provide an API key above, the default LLM config will be enabled immediately</li>
                <li>Additional LLM configs (if any) will need API keys configured separately in LLM Configs page</li>
                <li>OAuth-based integrations (Google Drive, Gmail, etc.) will require re-authorization</li>
                <li>The cloned agent starts with zero usage statistics</li>
                <li>MCP servers and webhooks are not cloned automatically</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Success Message */}
        {success && (
          <div className="bg-blush-wash border border-blush rounded-lg p-4">
            <div className="flex">
              <CheckCircle2 className="h-5 w-5 text-leaf mr-3 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-medium text-wine mb-1">Agent cloned successfully!</h4>
                <p className="text-sm text-wine">Redirecting to configuration page…</p>
                {warnings.length > 0 && (
                  <ul className="list-disc list-inside mt-2 space-y-1 text-sm text-wine">
                    {warnings.map((warning, idx) => (
                      <li key={idx}>{warning}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </AgentPageShell>
  )
}
