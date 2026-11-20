'use client'

import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { Monitor, ChevronRight, Wrench } from 'lucide-react'
import { TriggerSourceBadge } from './TriggerSourceBadge'
import type { ExecutionSummary } from '@/lib/api/live-lab'

interface ActiveExecutionsListProps {
  executions: ExecutionSummary[]
}

function ElapsedTimer({ startedAt }: { startedAt: string }) {
  const [elapsed, setElapsed] = useState('')

  useEffect(() => {
    const update = () => {
      const diff = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000)
      if (diff < 60) setElapsed(`${diff}s`)
      else if (diff < 3600) setElapsed(`${Math.floor(diff / 60)}m ${diff % 60}s`)
      else setElapsed(`${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}m`)
    }
    update()
    const interval = setInterval(update, 1000)
    return () => clearInterval(interval)
  }, [startedAt])

  return <span className="font-mono text-leaf text-xs">{elapsed}</span>
}

export function ActiveExecutionsList({ executions }: ActiveExecutionsListProps) {
  const router = useRouter()

  if (executions.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-sm border-2 border-dashed border-taupe p-10 text-center">
        <Monitor className="w-12 h-12 text-ash mx-auto mb-3" />
        <h3 className="text-base font-semibold text-ink mb-2">No agents running right now</h3>
        <p className="text-sm text-ink-soft max-w-sm mx-auto">
          Agents triggered from chat, Slack, WhatsApp, scheduler, and other channels will appear here in real-time.
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {executions.map((exec) => (
        <button
          key={exec.id}
          onClick={() => router.push(`/live-lab/${exec.id}`)}
          className="bg-white rounded-lg shadow-sm border border-line hover:shadow-md transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:border-blush text-left group"
        >
          <div className="p-4">
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-start gap-2.5 flex-1 min-w-0">
                <div className="relative flex-shrink-0">
                  <div className="w-9 h-9 bg-ink rounded-lg flex items-center justify-center text-white font-bold text-sm">
                    {exec.agent_name.charAt(0).toUpperCase()}
                  </div>
                  <span className="absolute -top-0.5 -right-0.5 w-3 h-3 bg-leaf rounded-full border-2 border-white motion-safe:animate-pulse" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-base font-semibold text-ink mb-0.5 truncate" title={exec.agent_name}>
                    {exec.agent_name}
                  </h3>
                  <TriggerSourceBadge source={exec.trigger_source} detail={exec.trigger_detail} />
                </div>
              </div>
            </div>

            {/* Message preview */}
            {exec.message_preview && (
              <p className="text-xs text-ink-soft mb-3 line-clamp-2">
                &ldquo;{exec.message_preview}&rdquo;
              </p>
            )}

            {/* Metrics */}
            <div className="text-xs text-ink-mute mb-3 p-2.5 bg-cream rounded-lg flex items-center justify-between">
              <div className="flex items-center gap-1">
                <Wrench className="w-3 h-3" />
                <span className="text-ink-soft font-medium">{exec.total_tools}</span> tools
              </div>
              <ElapsedTimer startedAt={exec.started_at} />
            </div>

            {/* View button */}
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-leaf-wash text-forest">
                <span className="w-1.5 h-1.5 rounded-full bg-leaf motion-safe:animate-pulse" />
                Running
              </span>
              <ChevronRight className="w-4 h-4 text-ash group-hover:text-leaf transition-colors" />
            </div>
          </div>
        </button>
      ))}
    </div>
  )
}
