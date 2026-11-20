'use client'

import { useRouter } from 'next/navigation'
import { CheckCircle, XCircle, Clock, AlertCircle, ChevronRight, Wrench, Coins } from 'lucide-react'
import { TriggerSourceBadge } from './TriggerSourceBadge'
import { cn } from '@/lib/utils/cn'
import type { ExecutionSummary } from '@/lib/api/live-lab'

interface RecentExecutionsListProps {
  executions: ExecutionSummary[]
}

function formatDuration(startedAt: string, completedAt: string): string {
  if (!completedAt) return '-'
  const ms = new Date(completedAt).getTime() - new Date(startedAt).getTime()
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

function formatTime(iso: string): string {
  if (!iso) return '-'
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHrs = Math.floor(diffMin / 60)
  if (diffHrs < 24) return `${diffHrs}h ago`
  return d.toLocaleDateString()
}

const STATUS_CONFIG: Record<string, { label: string; icon: React.ReactNode; className: string }> = {
  complete: {
    label: 'Success',
    icon: <CheckCircle className="w-3 h-3" />,
    className: 'bg-leaf-wash text-forest',
  },
  error: {
    label: 'Error',
    icon: <XCircle className="w-3 h-3" />,
    className: 'bg-blush-wash text-wine',
  },
  cancelled: {
    label: 'Cancelled',
    icon: <AlertCircle className="w-3 h-3" />,
    className: 'bg-sand text-ink',
  },
  running: {
    label: 'Running',
    icon: <Clock className="w-3 h-3" />,
    className: 'bg-sand-deep text-gold',
  },
}

export function RecentExecutionsList({ executions }: RecentExecutionsListProps) {
  const router = useRouter()

  if (executions.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-sm border-2 border-dashed border-taupe p-10 text-center">
        <Clock className="w-12 h-12 text-ash mx-auto mb-3" />
        <h3 className="text-base font-semibold text-ink mb-2">No recent executions</h3>
        <p className="text-sm text-ink-soft">
          Completed agent executions will appear here.
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {executions.map((exec) => {
        const statusInfo = STATUS_CONFIG[exec.status] || STATUS_CONFIG.complete
        return (
          <button
            key={exec.id}
            onClick={() => router.push(`/live-lab/${exec.id}`)}
            className="bg-white rounded-lg shadow-sm border border-line hover:shadow-md transition-[color,background-color,border-color,box-shadow,opacity,transform] hover:border-blush text-left group"
          >
            <div className="p-4">
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-start gap-2.5 flex-1 min-w-0">
                  <div className="w-9 h-9 bg-ink rounded-lg flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
                    {exec.agent_name.charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-base font-semibold text-ink mb-0.5 truncate" title={exec.agent_name}>
                      {exec.agent_name}
                    </h3>
                    <TriggerSourceBadge source={exec.trigger_source} />
                  </div>
                </div>
              </div>

              {/* Status Badge */}
              <div className="mb-3">
                <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium', statusInfo.className)}>
                  {statusInfo.icon}
                  {statusInfo.label}
                </span>
              </div>

              {/* Message preview */}
              {exec.message_preview && (
                <p className="text-xs text-ink-soft mb-3 line-clamp-2">
                  {exec.message_preview}
                </p>
              )}

              {/* Metrics */}
              <div className="text-xs text-ink-mute mb-3 space-y-0.5 p-2.5 bg-cream rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    Duration
                  </span>
                  <span className="font-mono text-ink-soft">{formatDuration(exec.started_at, exec.completed_at)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Wrench className="w-3 h-3" />
                    Tools
                  </span>
                  <span className="text-ink-soft font-medium">{exec.total_tools}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Coins className="w-3 h-3" />
                    Tokens
                  </span>
                  <span className="font-mono text-ink-soft">{exec.total_tokens.toLocaleString()}</span>
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-ink-mute">{formatTime(exec.completed_at || exec.started_at)}</span>
                <ChevronRight className="w-4 h-4 text-ash group-hover:text-leaf transition-colors" />
              </div>
            </div>
          </button>
        )
      })}
    </div>
  )
}
