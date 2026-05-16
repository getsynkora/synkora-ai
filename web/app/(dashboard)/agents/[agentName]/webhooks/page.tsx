'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { 
  Webhook, 
  Plus,
  List,
  Activity
} from 'lucide-react'
import { WebhookList, WebhookForm, WebhookEvents } from '@/components/webhooks'
import AgentPageShell, { AgentPagePanel, AgentPageTabs } from '@/components/agents/AgentPageShell'

type TabType = 'list' | 'create' | 'events'

export default function AgentWebhooksPage() {
  const params = useParams()
  const agentName = decodeURIComponent(params?.agentName as string || '')
  const [activeTab, setActiveTab] = useState<TabType>('list')
  const [refreshKey, setRefreshKey] = useState(0)

  const handleWebhookCreated = () => {
    setActiveTab('list')
    setRefreshKey(prev => prev + 1)
  }

  const handleCreateClick = () => {
    setActiveTab('create')
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Webhooks"
      description={<>Manage webhook integrations for <span className="font-semibold text-gray-900">{agentName}</span>.</>}
      icon={Webhook}
      badge="Automation Hooks"
      actions={activeTab === 'list' ? (
        <button
          onClick={handleCreateClick}
          className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
        >
          <Plus className="w-4 h-4" />
          Add Webhook
        </button>
      ) : undefined}
    >
      <div className="mb-6">
        <AgentPageTabs
          activeId={activeTab}
          onChange={(id) => setActiveTab(id as TabType)}
          items={[
            { id: 'list', label: 'Webhooks', icon: <List className="w-4 h-4" /> },
            { id: 'events', label: 'Event History', icon: <Activity className="w-4 h-4" /> },
            ...(activeTab === 'create' ? [{ id: 'create', label: 'Create Webhook', icon: <Plus className="w-4 h-4" /> }] : []),
          ]}
        />
      </div>

      <AgentPagePanel className="overflow-hidden">
          {activeTab === 'list' && (
            <WebhookList
              agentName={agentName}
              refreshKey={refreshKey}
              onCreateClick={handleCreateClick}
            />
          )}
          {activeTab === 'create' && (
            <WebhookForm
              agentName={agentName}
              onSuccess={handleWebhookCreated}
              onCancel={() => setActiveTab('list')}
            />
          )}
          {activeTab === 'events' && (
            <WebhookEvents agentName={agentName} />
          )}
      </AgentPagePanel>
    </AgentPageShell>
  )
}
