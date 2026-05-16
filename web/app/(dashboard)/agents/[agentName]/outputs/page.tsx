'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { 
  Send, 
  ArrowLeft, 
  Plus,
  List
} from 'lucide-react'
import { OutputConfigList, OutputConfigForm } from '@/components/agent-outputs'
import { useAgentOutputs } from '@/hooks/useAgentOutputs'
import { apiClient } from '@/lib/api/client'
import type { OutputConfig, CreateOutputConfigData } from '@/types/agent-outputs'
import toast from 'react-hot-toast'
import AgentPageShell, { AgentPagePanel, AgentPageTabs } from '@/components/agents/AgentPageShell'

type TabType = 'list' | 'create' | 'edit'

export default function AgentOutputsPage() {
  const params = useParams()
  const agentName = decodeURIComponent(params?.agentName as string || '')
  const [activeTab, setActiveTab] = useState<TabType>('list')
  const [refreshKey, setRefreshKey] = useState(0)
  const [editingConfig, setEditingConfig] = useState<OutputConfig | undefined>()
  const [agentId, setAgentId] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const { createOutput, updateOutput } = useAgentOutputs(agentId)

  // Fetch agent to get ID
  useEffect(() => {
    const fetchAgent = async () => {
      try {
        setLoading(true)
        const agent = await apiClient.getAgent(agentName)
        setAgentId(agent.id)
      } catch (error) {
        toast.error('Failed to load agent')
        console.error('Error fetching agent:', error)
      } finally {
        setLoading(false)
      }
    }

    if (agentName) {
      fetchAgent()
    }
  }, [agentName])

  const handleOutputSubmit = async (data: CreateOutputConfigData) => {
    try {
      if (editingConfig) {
        await updateOutput(editingConfig.id, data)
        toast.success('Output configuration updated successfully')
      } else {
        await createOutput(data)
        toast.success('Output configuration created successfully')
      }
      setActiveTab('list')
      setEditingConfig(undefined)
      setRefreshKey(prev => prev + 1)
    } catch (error: any) {
      toast.error(error.message || 'Failed to save output configuration')
      throw error
    }
  }

  const handleCreateClick = () => {
    setEditingConfig(undefined)
    setActiveTab('create')
  }

  const handleEditClick = (config: OutputConfig) => {
    setEditingConfig(config)
    setActiveTab('edit')
  }

  const handleCancel = () => {
    setActiveTab('list')
    setEditingConfig(undefined)
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Output Configurations"
      description={<>Route agent responses to Slack, email, or webhooks for <span className="font-semibold text-gray-900">{agentName}</span>.</>}
      icon={Send}
      badge="Response Routing"
      actions={activeTab === 'list' ? (
        <button
          onClick={handleCreateClick}
          className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
        >
          <Plus className="w-4 h-4" />
          Add Output
        </button>
      ) : undefined}
    >
      <div className="mb-6">
        <AgentPageTabs
          activeId={activeTab}
          onChange={(id) => setActiveTab(id as TabType)}
          items={[
            { id: 'list', label: 'Output Configurations', icon: <List className="w-4 h-4" /> },
            ...(activeTab === 'create' ? [{ id: 'create', label: 'Create Output', icon: <Plus className="w-4 h-4" /> }] : []),
            ...(activeTab === 'edit' ? [{ id: 'edit', label: 'Edit Output', icon: <Plus className="w-4 h-4" /> }] : []),
          ]}
        />
      </div>

      <AgentPagePanel className="overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-500">Loading agent...</div>
          ) : agentId ? (
            <>
              {activeTab === 'list' && (
                <OutputConfigList
                  agentId={agentId}
                  refreshKey={refreshKey}
                  onCreateClick={handleCreateClick}
                  onEditClick={handleEditClick}
                />
              )}
              {(activeTab === 'create' || activeTab === 'edit') && (
                <OutputConfigForm
                  output={editingConfig}
                  onSubmit={handleOutputSubmit}
                  onCancel={handleCancel}
                />
              )}
            </>
          ) : (
            <div className="p-8 text-center text-red-500">Failed to load agent</div>
          )}
      </AgentPagePanel>
    </AgentPageShell>
  )
}
