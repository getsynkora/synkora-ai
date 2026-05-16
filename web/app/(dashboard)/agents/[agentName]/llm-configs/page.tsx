'use client'

import { useState, useEffect } from 'react'
import { useParams} from 'next/navigation'
import { Brain, X, AlertTriangle } from 'lucide-react'
import toast from 'react-hot-toast'
import { LLMConfigForm, LLMConfigList } from '@/components/agents/llm-configs'
import RoutingModePanel from '@/components/agents/llm-configs/RoutingModePanel'
import { useLLMConfigManager } from '@/hooks/useAgentLLMConfigs'
import { AgentLLMConfig, AgentLLMConfigCreate, AgentLLMConfigUpdate, RoutingMode } from '@/types/agent-llm-config'
import { updateAgent, getAgent } from '@/lib/api/agents'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

export default function AgentLLMConfigsPage() {
  const params = useParams()
  const agentName = params.agentName as string

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
  const [deletingConfigId, setDeletingConfigId] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [routingMode, setRoutingMode] = useState<RoutingMode>('fixed')
  const [routingConfig, setRoutingConfig] = useState<Record<string, any>>({})

  // Load current routing settings from agent
  useEffect(() => {
    if (!agentName) return
    getAgent(agentName).then((agent: any) => {
      if (agent?.routing_mode) setRoutingMode(agent.routing_mode as RoutingMode)
      if (agent?.routing_config) setRoutingConfig(agent.routing_config)
    }).catch(() => {/* agent may not exist yet */})
  }, [agentName])

  const handleSaveRouting = async (mode: RoutingMode, config: Record<string, any>) => {
    await updateAgent(agentName, { routing_mode: mode, routing_config: config })
    setRoutingMode(mode)
    setRoutingConfig(config)
    toast.success('Routing mode updated')
  }

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

  const handleDelete = (configId: string) => {
    setDeletingConfigId(configId)
  }

  const confirmDelete = async () => {
    if (!deletingConfigId) return
    setIsDeleting(true)
    try {
      await deleteConfig(deletingConfigId)
      toast.success('Configuration deleted successfully')
      setDeletingConfigId(null)
    } catch (error: any) {
      toast.error(error.message || 'Failed to delete configuration')
    } finally {
      setIsDeleting(false)
    }
  }

  const handleSetDefault = async (configId: string) => {
    try {
      await setDefaultConfig(configId)
      toast.success('Default configuration updated')
    } catch (error: any) {
      toast.error(error.message || 'Failed to set default configuration')
    }
  }

  const handleToggleEnabled = async (configId: string, enabled: boolean) => {
    try {
      await updateConfig(configId, { enabled })
      toast.success(`Configuration ${enabled ? 'enabled' : 'disabled'}`)
    } catch (error: any) {
      toast.error(error.message || 'Failed to update configuration')
    }
  }


  const deletingConfig = configs.find(c => c.id === deletingConfigId)

  return (
    <div className="dashboard-resource-page min-h-screen">
      {/* Delete Confirmation Modal */}
      {deletingConfigId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[1.8rem] border border-black/10 bg-[#fcfaf5] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.18)]">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-[1rem] bg-red-50">
                <AlertTriangle className="w-5 h-5 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Delete Configuration</h3>
            </div>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete{' '}
              <span className="font-medium text-gray-900">
                {deletingConfig?.name || 'this configuration'}
              </span>
              ? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeletingConfigId(null)}
                disabled={isDeleting}
                className="rounded-[1rem] border border-black/10 bg-[#f1eadc] px-4 py-2.5 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={isDeleting}
                className="flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-black disabled:opacity-50"
              >
                {isDeleting && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      <AgentPageShell
        agentName={agentName}
        title="AI Model Config"
        description={<>Manage AI models for <span className="font-semibold text-gray-900">{agentName}</span>.</>}
        icon={Brain}
        backHref={`/agents/${agentName}/view`}
        backLabel="Back to Agent"
        badge="Model Routing"
      >
        {showForm ? (
          <AgentPagePanel className="p-6">
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
          </AgentPagePanel>
        ) : (
          <div>
            {/* Routing mode panel */}
            <RoutingModePanel
              agentName={agentName}
              currentMode={routingMode}
              routingConfig={routingConfig}
              onSave={handleSaveRouting}
            />

            <AgentPagePanel className="p-6">
              <div className="mb-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-2">
                  Model Configurations
                </h2>
                <p className="text-sm text-gray-600">
                  Add multiple models and configure routing rules on each to control which queries
                  each model handles. The routing mode above determines how the agent picks between them.
                </p>
              </div>

              <LLMConfigList
                configs={configs}
                onAdd={handleAdd}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onSetDefault={handleSetDefault}
                onToggleEnabled={handleToggleEnabled}
                isLoading={isLoading}
              />
            </AgentPagePanel>
          </div>
        )}
      </AgentPageShell>
    </div>
  )
}
