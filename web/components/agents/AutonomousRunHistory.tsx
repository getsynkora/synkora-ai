'use client'

import { CheckCircle, XCircle, Clock, ChevronDown, ChevronUp, ShieldAlert } from 'lucide-react'
import { useState } from 'react'

interface RunRecord {
  id: string
  status: string
  started_at: string
  completed_at?: string
  execution_time_seconds?: number
  error_message?: string
  output_preview?: string
}

interface Props {
  runs: RunRecord[]
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const secs = Math.floor(diff / 1000)
  if (secs < 60) return `${secs}s ago`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins} min ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hr ago`
  return `${Math.floor(hrs / 24)} days ago`
}

function statusMeta(status: string) {
  switch (status) {
    case 'success':
      return { icon: <CheckCircle className="w-4 h-4 text-leaf" />, badge: 'bg-leaf-wash text-forest', label: 'success' }
    case 'running':
      return { icon: <Clock className="w-4 h-4 text-azure motion-safe:animate-pulse" />, badge: 'bg-sky-wash text-azure', label: 'running' }
    case 'awaiting_approval':
      return { icon: <ShieldAlert className="w-4 h-4 text-warn" />, badge: 'bg-sand-deep text-gold', label: 'awaiting approval' }
    default:
      return { icon: <XCircle className="w-4 h-4 text-leaf" />, badge: 'bg-blush-wash text-danger', label: status }
  }
}

function RunRow({ run, index }: { run: RunRecord; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const { icon, badge, label } = statusMeta(run.status)

  return (
    <div className="border-b border-sand last:border-0">
      <div
        className="flex items-center gap-4 px-4 py-3 hover:bg-cream cursor-pointer select-none"
        onClick={() => setExpanded(e => !e)}
      >
        {/* Status icon */}
        <div className="flex-shrink-0">{icon}</div>

        {/* Run number & status */}
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-ink">
            Run #{index + 1}
          </span>
          <span className={`ml-2 text-xs px-1.5 py-0.5 rounded-full font-medium ${badge}`}>
            {label}
          </span>
        </div>

        {/* Timing */}
        <div className="text-xs text-ink-mute text-right flex-shrink-0">
          <div>{timeAgo(run.started_at)}</div>
          {run.execution_time_seconds != null && (
            <div>{run.execution_time_seconds.toFixed(1)}s</div>
          )}
        </div>

        <div className="flex-shrink-0 text-ash">
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </div>

      {expanded && (
        <div className="px-12 pb-3">
          {run.error_message ? (
            <div className="rounded bg-blush-wash border border-blush px-3 py-2 text-xs text-danger font-mono whitespace-pre-wrap">
              {run.error_message}
            </div>
          ) : run.output_preview ? (
            <div className="rounded bg-cream border border-line px-3 py-2 text-xs text-ink-soft whitespace-pre-wrap">
              {run.output_preview}
            </div>
          ) : (
            <div className="rounded bg-cream border border-line px-3 py-2 text-xs text-ash italic">
              No text output, agent completed via tool calls only.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function AutonomousRunHistory({ runs }: Props) {
  if (runs.length === 0) {
    return (
      <div className="py-10 text-center text-sm text-ink-mute">
        No runs yet. Enable autonomous mode and click Run Now to start.
      </div>
    )
  }

  return (
    <div className="divide-y divide-sand">
      {runs.map((run, i) => (
        <RunRow key={run.id} run={run} index={runs.length - 1 - i} />
      ))}
    </div>
  )
}
