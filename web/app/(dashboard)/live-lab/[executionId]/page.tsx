'use client'

import { useEffect, useRef, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { useLiveLabStore } from '@/lib/store/liveLabStore'
import { getExecution, getExecutionStreamUrl } from '@/lib/api/live-lab'
import type { ExecutionEvent } from '@/lib/api/live-lab'
import { secureStorage } from '@/lib/auth/secure-storage'
import { Activity, AlertTriangle } from 'lucide-react'
import { MetricsBar } from '@/components/live-lab/MetricsBar'
import { ActivityFeed } from '@/components/live-lab/ActivityFeed'
import { LiveWorkspace } from '@/components/live-lab/LiveWorkspace'
import { ExecutionPlan } from '@/components/live-lab/ExecutionPlan'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

export default function ExecutionDetailPage() {
  const params = useParams()
  const executionId = params.executionId as string

  const {
    currentExecution,
    initCurrentExecution,
    clearCurrentExecution,
    appendEvent,
  } = useLiveLabStore()

  const abortRef = useRef<AbortController | null>(null)

  const startStream = useCallback(
    async (execId: string) => {
      const token = secureStorage.getAccessToken()
      const url = getExecutionStreamUrl(execId)

      abortRef.current = new AbortController()

      try {
        const response = await fetch(url, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: abortRef.current.signal,
        })

        if (!response.ok || !response.body) return

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (!line.trim() || !line.startsWith('data: ')) continue
            try {
              const event: ExecutionEvent = JSON.parse(line.slice(6))
              if (event.type === 'stream_end') return
              appendEvent(event)
            } catch {
              // skip malformed events
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        console.error('Stream error:', err)
      }
    },
    [appendEvent],
  )

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const exec = await getExecution(executionId)
        if (cancelled) return

        initCurrentExecution(exec)

        // Load stored events for completed executions
        if (exec.events && exec.events.length > 0) {
          for (const event of exec.events) {
            appendEvent(event)
          }
        }

        // If still running, start SSE stream for new events
        if (exec.status === 'running') {
          startStream(executionId)
        }
      } catch (err) {
        console.error('Failed to load execution:', err)
      }
    }

    load()

    return () => {
      cancelled = true
      abortRef.current?.abort()
      clearCurrentExecution()
    }
  }, [executionId, initCurrentExecution, clearCurrentExecution, appendEvent, startStream])

  if (!currentExecution) {
    return (
      <div className="dashboard-resource-page flex min-h-screen items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-200 border-t-[#171717]" />
      </div>
    )
  }

  const isLive = currentExecution.status === 'running'
  const shortExecutionId = currentExecution.id.slice(0, 8)
  const statusLabel =
    currentExecution.status === 'running'
      ? 'Live'
      : currentExecution.status === 'complete'
        ? 'Completed'
        : currentExecution.status === 'error'
          ? 'Error'
          : 'Cancelled'

  return (
    <DashboardPageShell
      title={currentExecution.agentName}
      description={
        currentExecution.messagePreview ? (
          <>
            <span className="font-medium text-gray-900">&ldquo;{currentExecution.messagePreview}&rdquo;</span>
            <span className="text-gray-500"> Live execution workspace, event timeline, and tool trace for this run.</span>
          </>
        ) : (
          'Live execution workspace, event timeline, and tool trace for this run.'
        )
      }
      icon={Activity}
      badge="Live Lab Session"
      maxWidthClassName="max-w-[1500px]"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Live Lab', href: '/live-lab' },
        { label: currentExecution.agentName },
      ]}
      stats={[
        { label: 'Status', value: statusLabel },
        { label: 'Trigger', value: currentExecution.triggerSource },
        { label: 'Session', value: shortExecutionId },
      ]}
    >
      <DashboardPagePanel className="mb-6 overflow-hidden">
        <MetricsBar
          startedAt={currentExecution.metrics.startedAt}
          completedAt={currentExecution.metrics.completedAt || undefined}
          status={currentExecution.status}
          tokens={currentExecution.metrics.tokens}
          toolCount={currentExecution.metrics.toolCount}
          cost={currentExecution.metrics.cost}
          triggerSource={currentExecution.triggerSource}
          triggerDetail={currentExecution.triggerDetail || undefined}
          agentName={currentExecution.agentName}
          messagePreview={currentExecution.messagePreview}
        />
      </DashboardPagePanel>

      <DashboardPagePanel className="overflow-hidden p-3">
        <div className="grid min-h-[72vh] gap-3 xl:grid-cols-[280px_minmax(0,1fr)_260px]">
          <div className="hidden min-h-[24rem] overflow-hidden rounded-[1.6rem] border border-[#eadfce] bg-[linear-gradient(180deg,_rgba(249,244,236,0.98),_rgba(255,255,255,0.92))] md:flex">
            <ActivityFeed events={currentExecution.events} isLive={isLive} />
          </div>

          <div className="min-h-[32rem] overflow-hidden rounded-[1.75rem] border border-[#eadfce] bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(248,242,233,0.96))] shadow-[0_22px_55px_-44px_rgba(76,52,31,0.4)]">
            <LiveWorkspace content={currentExecution.workspaceContent} isStreaming={isLive} />
          </div>

          <div className="hidden min-h-[24rem] overflow-hidden rounded-[1.6rem] border border-[#eadfce] bg-[linear-gradient(180deg,_rgba(255,255,255,0.96),_rgba(246,239,230,0.92))] xl:flex">
            <ExecutionPlan
              events={currentExecution.events}
              activeTools={currentExecution.activeTools}
              isLive={isLive}
            />
          </div>
        </div>
      </DashboardPagePanel>

      {currentExecution.status === 'error' && currentExecution.error ? (
        <DashboardPagePanel className="mt-6 border-[#efd8dd] bg-[linear-gradient(180deg,_rgba(253,245,246,0.98),_rgba(250,238,240,0.94))] p-4">
          <div className="flex items-start gap-3">
            <div className="rounded-[1rem] bg-[#f7dfe5] p-2 text-[#a04560]">
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-[#6d2439]">Execution error</p>
              <p className="mt-1 text-sm leading-6 text-[#8a445c]">{currentExecution.error}</p>
            </div>
          </div>
        </DashboardPagePanel>
      ) : null}
    </DashboardPageShell>
  )
}
