'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import toast from 'react-hot-toast'
import { ArrowLeft, Copy, AlertTriangle, CheckCircle2, Cpu } from 'lucide-react'
import { apiClient } from '@/lib/api/client'

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
    <div className="min-h-screen bg-gradient-to-br from-red-50/60 via-white to-rose-50/40 p-4 md:p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft size={20} />
            Back
          </button>
          <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Clone Agent</h1>
          <p className="text-gray-600 mt-2">
            Create a copy of "{decodeURIComponent(agentName)}" with customizable settings
          </p>
        </div>

        {/* Main Content */}
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <div className="p-4 md:p-8">
            <div className="space-y-6 max-w-3xl">
              {/* Agent Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  New Agent Name *
                </label>
                <input
                  type="text"
                  value={formData.new_name}
                  onChange={(e) => setFormData({ ...formData, new_name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all duration-200"
                  placeholder="Enter new agent name"
                  required
                />
                <p className="mt-1 text-sm text-gray-500">
                  A unique name for your cloned agent
                </p>
              </div>

              {/* API Key */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  New API Key (Optional)
                </label>

                {/* Show LLM Config Info */}
                {loadingConfigs ? (
                  <div className="mb-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="animate-pulse flex items-center gap-2">
                      <div className="h-4 w-4 bg-gray-300 rounded"></div>
                      <div className="h-4 w-32 bg-gray-300 rounded"></div>
                    </div>
                  </div>
                ) : defaultConfig ? (
                  <div className="mb-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <div className="flex items-center gap-2">
                      <Cpu className="h-4 w-4 text-blue-600" />
                      <span className="text-sm text-blue-900">
                        This agent uses <span className="font-semibold">{defaultConfig.provider}</span> provider with model <span className="font-semibold">{defaultConfig.model_name}</span>
                      </span>
                    </div>
                    {llmConfigs.length > 1 && (
                      <p className="text-xs text-blue-700 mt-1 ml-6">
                        + {llmConfigs.length - 1} more LLM config(s) that will need API keys configured separately
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="mb-3 p-3 bg-yellow-50 rounded-lg border border-yellow-200">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-yellow-600" />
                      <span className="text-sm text-yellow-900">
                        No LLM configuration found for this agent
                      </span>
                    </div>
                  </div>
                )}

                <input
                  type="password"
                  value={formData.new_api_key}
                  onChange={(e) => setFormData({ ...formData, new_api_key: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all duration-200"
                  placeholder={defaultConfig ? `Enter your ${defaultConfig.provider} API key` : "Leave empty to configure later"}
                />
                <p className="mt-1 text-sm text-gray-500">
                  {defaultConfig
                    ? `Provide your ${defaultConfig.provider} API key to enable the cloned agent immediately`
                    : "Configure LLM settings after cloning"
                  }
                </p>
              </div>

              {/* Clone Options */}
              <div className="border-t border-gray-200 pt-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Clone Options</h3>
                <div className="space-y-4">
                  {/* Clone Tools */}
                  <div className="flex items-start justify-between">
                    <div className="flex-grow">
                      <label htmlFor="clone_tools" className="block text-sm font-medium text-gray-700">
                        Clone Tool Configurations
                      </label>
                      <p className="text-sm text-gray-500 mt-1">
                        Copy all tool settings and configurations
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      id="clone_tools"
                      checked={formData.clone_tools}
                      onChange={(e) => setFormData({ ...formData, clone_tools: e.target.checked })}
                      className="mt-1 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                    />
                  </div>

                  {/* Clone Knowledge Bases */}
                  <div className="flex items-start justify-between">
                    <div className="flex-grow">
                      <label htmlFor="clone_knowledge_bases" className="block text-sm font-medium text-gray-700">
                        Clone Knowledge Base Links
                      </label>
                      <p className="text-sm text-gray-500 mt-1">
                        Link same knowledge bases (OAuth sources need re-auth)
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      id="clone_knowledge_bases"
                      checked={formData.clone_knowledge_bases}
                      onChange={(e) => setFormData({ ...formData, clone_knowledge_bases: e.target.checked })}
                      className="mt-1 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                    />
                  </div>

                  {/* Clone Sub-agents */}
                  <div className="flex items-start justify-between">
                    <div className="flex-grow">
                      <label htmlFor="clone_sub_agents" className="block text-sm font-medium text-gray-700">
                        Clone Sub-agent Relationships
                      </label>
                      <p className="text-sm text-gray-500 mt-1">
                        Copy all sub-agent connections and configs
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      id="clone_sub_agents"
                      checked={formData.clone_sub_agents}
                      onChange={(e) => setFormData({ ...formData, clone_sub_agents: e.target.checked })}
                      className="mt-1 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                    />
                  </div>

                  {/* Clone Workflows */}
                  <div className="flex items-start justify-between">
                    <div className="flex-grow">
                      <label htmlFor="clone_workflows" className="block text-sm font-medium text-gray-700">
                        Clone Workflow Configurations
                      </label>
                      <p className="text-sm text-gray-500 mt-1">
                        Copy ADK workflow settings if enabled
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      id="clone_workflows"
                      checked={formData.clone_workflows}
                      onChange={(e) => setFormData({ ...formData, clone_workflows: e.target.checked })}
                      className="mt-1 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                    />
                  </div>
                </div>
              </div>

              {/* Important Notes */}
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <div className="flex">
                  <AlertTriangle className="h-5 w-5 text-yellow-600 mr-3 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-medium text-yellow-900 mb-2">Important Notes</h4>
                    <ul className="list-disc list-inside space-y-1 text-sm text-yellow-800">
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
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div className="flex">
                    <CheckCircle2 className="h-5 w-5 text-green-600 mr-3 flex-shrink-0 mt-0.5" />
                    <div>
                      <h4 className="text-sm font-medium text-green-900 mb-1">Agent cloned successfully!</h4>
                      <p className="text-sm text-green-800">Redirecting to configuration page...</p>
                      {warnings.length > 0 && (
                        <ul className="list-disc list-inside mt-2 space-y-1 text-sm text-green-800">
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
          </div>

          {/* Footer */}
          <div className="border-t border-gray-200 px-8 py-4 bg-gray-50 flex justify-between items-center">
            <div className="text-sm text-gray-600">
              Ready to clone your agent
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => router.back()}
                disabled={cloning || success}
                className="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={cloning || success || !formData.new_name}
                className="px-6 py-2 bg-gradient-to-r from-primary-500 to-primary-600 text-white rounded-lg hover:from-primary-600 hover:to-primary-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm hover:shadow-md flex items-center gap-2"
              >
                {cloning ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    Cloning...
                  </>
                ) : (
                  <>
                    <Copy size={16} />
                    Clone Agent
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
