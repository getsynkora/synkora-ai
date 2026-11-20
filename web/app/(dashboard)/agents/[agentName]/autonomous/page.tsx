'use client'

import { useEffect, useState, useCallback } from 'react'
import { extractErrorMessage } from '@/lib/api/error'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Bot, Settings, History, Brain, ToggleLeft, ToggleRight, ShieldCheck } from 'lucide-react'
import { AutonomousConfig } from '@/components/agents/AutonomousConfig'
import { AutonomousRunHistory } from '@/components/agents/AutonomousRunHistory'
import { AutonomousMemoryViewer } from '@/components/agents/AutonomousMemoryViewer'
import { AutonomousApprovals } from '@/components/agents/AutonomousApprovals'
import AgentPageShell, { AgentPagePanel, AgentPageTabs } from '@/components/agents/AgentPageShell'

type Tab = 'config' | 'history' | 'memory' | 'approvals'

interface AutonomousStatus {
  enabled: boolean
  task_id?: string
  goal?: string
  schedule?: string
  schedule_type?: string
  max_steps?: number
  is_active?: boolean
  last_run_at?: string
  next_run_at?: string
  recent_runs: RunRecord[]
  // HITL
  require_approval?: boolean
  approval_mode?: string
  require_approval_tools?: string[]
  approval_channel?: string
  approval_channel_config?: Record<string, string>
  approval_timeout_minutes?: number
}

interface RunRecord {
  id: string
  status: string
  started_at: string
  completed_at?: string
  execution_time_seconds?: number
  error_message?: string
  output_preview?: string
}

interface MemoryMessage {
  id: string
  role: string
  content: string
  created_at: string
}

export default function AutonomousPage() {
  const params = useParams()
  const agentName = decodeURIComponent((params?.agentName as string) || '')

  const [activeTab, setActiveTab] = useState<Tab>('config')
  const [status, setStatus] = useState<AutonomousStatus | null>(null)
  const [memory, setMemory] = useState<MemoryMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toastMsg, setToastMsg] = useState<string | null>(null)
  const [pendingApprovals, setPendingApprovals] = useState(0)
  const [showDisableDialog, setShowDisableDialog] = useState(false)

  function showToast(msg: string) {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(null), 3000)
  }

  const fetchStatus = useCallback(async () => {
    try {
      const { apiClient } = await import('@/lib/api/client')
      const data = await apiClient.request(
        'GET',
        `/api/v1/agents/${encodeURIComponent(agentName)}/autonomous`
      )
      setStatus(data)
      setError(null)
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to load autonomous config'))
    } finally {
      setLoading(false)
    }
  }, [agentName])

  const fetchMemory = useCallback(async () => {
    try {
      const { apiClient } = await import('@/lib/api/client')
      const data = await apiClient.request(
        'GET',
        `/api/v1/agents/${encodeURIComponent(agentName)}/autonomous/memory`
      )
      setMemory(Array.isArray(data) ? data : [])
    } catch {
      setMemory([])
    }
  }, [agentName])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  useEffect(() => {
    if (activeTab === 'memory') {
      fetchMemory()
    }
  }, [activeTab, fetchMemory])

  async function handleToggleActive() {
    if (!status?.task_id) return
    try {
      const { apiClient } = await import('@/lib/api/client')
      await apiClient.request(
        'PATCH',
        `/api/v1/agents/${encodeURIComponent(agentName)}/autonomous`,
        { is_active: !status.is_active }
      )
      await fetchStatus()
      showToast(status.is_active ? 'Autonomous mode paused' : 'Autonomous mode resumed')
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Toggle failed'))
    }
  }

  async function handleDelete() {
    try {
      const { apiClient } = await import('@/lib/api/client')
      await apiClient.request(
        'DELETE',
        `/api/v1/agents/${encodeURIComponent(agentName)}/autonomous`
      )
      setShowDisableDialog(false)
      await fetchStatus()
      showToast('Autonomous mode disabled')
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Delete failed'))
    }
  }

  const tabs: { id: Tab; label: React.ReactNode; icon: React.ReactNode }[] = [
    { id: 'config', label: 'Configuration', icon: <Settings className="w-4 h-4" /> },
    { id: 'history', label: `Recent Runs${status?.recent_runs?.length ? ` (${status.recent_runs.length})` : ''}`, icon: <History className="w-4 h-4" /> },
    { id: 'memory', label: 'Memory', icon: <Brain className="w-4 h-4" /> },
    {
      id: 'approvals',
      label: (
        <span className="flex items-center gap-1.5">
          Approvals
          {pendingApprovals > 0 && (
            <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-warn text-white text-[10px] font-bold">
              {pendingApprovals}
            </span>
          )}
        </span>
      ),
      icon: <ShieldCheck className="w-4 h-4" />,
    },
  ]

  return (
    <AgentPageShell
      agentName={agentName}
      title="Autonomous Mode"
      description="Always-on daemon agent that runs on a schedule and maintains memory across runs."
      icon={Bot}
      badge="Background Automation"
      maxWidthClassName="max-w-[90rem]"
      stats={status?.task_id ? [
        { label: 'Status', value: status.is_active ? 'Active' : 'Paused' },
        { label: 'Approvals', value: pendingApprovals },
      ] : undefined}
      actions={status?.task_id ? (
        <>
          <button
            onClick={handleToggleActive}
            className="flex items-center gap-2 rounded-[1rem] border border-black/10 bg-white/80 px-4 py-3 text-sm font-semibold text-ink transition-colors hover:bg-white"
          >
            {status.is_active ? (
              <>
                <ToggleRight className="w-5 h-5 text-leaf" />
                Pause
              </>
            ) : (
              <>
                <ToggleLeft className="w-5 h-5 text-ash" />
                Resume
              </>
            )}
          </button>
          <button
            onClick={() => setShowDisableDialog(true)}
            className="rounded-[1rem] border border-blush bg-blush-wash px-4 py-3 text-sm font-semibold text-danger transition-colors hover:bg-blush-wash"
          >
            Delete
          </button>
        </>
      ) : undefined}
    >

        {/* Pending approvals banner */}
        {pendingApprovals > 0 && activeTab !== 'approvals' && (
          <button
            onClick={() => setActiveTab('approvals')}
            className="mb-4 w-full flex items-center gap-2 rounded-md bg-sand-deep border border-honey px-4 py-3 text-sm text-gold hover:bg-sand-deep transition-colors text-left"
          >
            <ShieldCheck className="w-4 h-4 text-warn flex-shrink-0" />
            <span>
              <strong>{pendingApprovals} action{pendingApprovals > 1 ? 's' : ''}</strong> waiting for your approval
            </span>
            <span className="ml-auto text-warn font-medium text-xs">Review</span>
          </button>
        )}

        {/* Toast */}
        {toastMsg && (
          <div className="mb-4 rounded-md bg-leaf-wash border border-mint px-4 py-3 text-sm text-forest">
            {toastMsg}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-4 rounded-md bg-blush-wash border border-blush px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-6 h-6 border-2 border-ink border-t-transparent rounded-full motion-safe:animate-spin" />
          </div>
        ) : !status?.task_id ? (
          /* No autonomous task configured — show setup form */
          <AgentPagePanel>
            <div className="p-6">
              <AutonomousConfig
                agentName={agentName}
                status={status ?? { enabled: false }}
                onSaved={async () => {
                  await fetchStatus()
                  showToast('Autonomous mode enabled')
                }}
                onTriggered={() => {
                  showToast('Run queued, check Recent Runs shortly')
                  setActiveTab('history')
                }}
              />
            </div>
          </AgentPagePanel>
        ) : (
          <AgentPagePanel className="overflow-hidden">
            <div className="border-b border-black/10 p-4">
              <AgentPageTabs
                activeId={activeTab}
                onChange={(id) => setActiveTab(id as Tab)}
                items={tabs.map((tab) => ({ id: tab.id, label: tab.label, icon: tab.icon }))}
              />
            </div>

            {/* Tab content */}
            <div className="p-6">
              {activeTab === 'config' && (
                <AutonomousConfig
                  agentName={agentName}
                  status={status}
                  onSaved={async () => {
                    await fetchStatus()
                    showToast('Saved')
                  }}
                  onTriggered={() => {
                    showToast('Run queued, check Recent Runs shortly')
                    setActiveTab('history')
                  }}
                />
              )}

              {activeTab === 'history' && (
                <AutonomousRunHistory runs={status.recent_runs ?? []} />
              )}

              {activeTab === 'memory' && (
                <AutonomousMemoryViewer
                  agentName={agentName}
                  messages={memory}
                  onCleared={async () => {
                    await fetchMemory()
                    showToast('Memory cleared')
                  }}
                />
              )}

              {activeTab === 'approvals' && (
                <AutonomousApprovals
                  agentName={agentName}
                  onCountChange={setPendingApprovals}
                />
              )}
            </div>
          </AgentPagePanel>
        )}


      {/* Disable confirmation dialog */}
      {showDisableDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowDisableDialog(false)} />
          <div className="relative w-full max-w-sm rounded-[1.8rem] border border-black/10 bg-cream p-6 shadow-soft">
            <div className="flex items-center gap-3 mb-4">
              <div className="rounded-[1rem] bg-sand-deep p-2.5">
                <Bot className="w-5 h-5 text-danger" />
              </div>
              <h2 className="text-base font-semibold text-ink">Delete Autonomous Task</h2>
            </div>
            <p className="text-sm text-ink-soft mb-6">
              This will permanently delete the autonomous schedule and all run history for <strong>{agentName}</strong>. This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDisableDialog(false)}
                className="rounded-[1rem] border border-black/10 bg-sand-deep px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-line"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="rounded-[1rem] bg-danger px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-danger"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </AgentPageShell>
  )
}
