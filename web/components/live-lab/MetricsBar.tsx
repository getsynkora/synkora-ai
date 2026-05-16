'use client'

import { useEffect, useState } from 'react'
import { Clock, Wrench, BarChart3, DollarSign } from 'lucide-react'
import { TriggerSourceBadge } from './TriggerSourceBadge'

interface MetricsBarProps {
  startedAt: string
  completedAt?: string
  status: string
  tokens: number
  toolCount: number
  cost: number
  triggerSource: string
  triggerDetail?: string
  agentName: string
  messagePreview?: string
}

function formatElapsed(startedAt: string, completedAt?: string): string {
  const start = new Date(startedAt).getTime()
  const end = completedAt ? new Date(completedAt).getTime() : Date.now()
  const seconds = Math.floor((end - start) / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remaining = seconds % 60
  if (minutes < 60) return `${minutes}m ${remaining}s`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}m`
}

export function MetricsBar({
  startedAt,
  completedAt,
  status,
  tokens,
  toolCount,
  cost,
  triggerSource,
  triggerDetail,
  agentName,
  messagePreview,
}: MetricsBarProps) {
  const [elapsed, setElapsed] = useState(() => formatElapsed(startedAt, completedAt))

  useEffect(() => {
    if (status !== 'running') {
      setElapsed(formatElapsed(startedAt, completedAt))
      return
    }
    const interval = setInterval(() => {
      setElapsed(formatElapsed(startedAt))
    }, 1000)
    return () => clearInterval(interval)
  }, [startedAt, completedAt, status])

  const statusConfig: Record<string, { label: string; color: string; dot: string }> = {
    running: {
      label: 'Live',
      color: 'border-[#cfe5d7] bg-[#edf7f1] text-[#24543b]',
      dot: 'bg-[#2b7a52]',
    },
    complete: {
      label: 'Completed',
      color: 'border-[#d7e1ef] bg-[#eef4fb] text-[#345c8a]',
      dot: 'bg-[#5f84b3]',
    },
    error: {
      label: 'Error',
      color: 'border-[#efd8dd] bg-[#fdf3f5] text-[#8a445c]',
      dot: 'bg-[#c55a78]',
    },
    cancelled: {
      label: 'Cancelled',
      color: 'border-[#e5ddd2] bg-[#f5f1ea] text-[#7b6f61]',
      dot: 'bg-[#a89a87]',
    },
  }

  const statusInfo = statusConfig[status] || statusConfig.running

  return (
    <div className="overflow-hidden">
      <div className="flex flex-col gap-4 px-5 py-5 md:flex-row md:items-start md:justify-between md:px-6">
        <div className="flex min-w-0 items-start gap-3.5">
          <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-[1.15rem] bg-[#171717] text-sm font-semibold text-[#f8f4ec] shadow-[0_16px_32px_-24px_rgba(0,0,0,0.55)]">
            {agentName.charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center rounded-full border border-[#dfd1be] bg-[#f8f1e4] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#8c6b4d]">
                Execution overview
              </span>
              <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${statusInfo.color}`}>
                <span className={`h-2 w-2 rounded-full ${statusInfo.dot} ${status === 'running' ? 'animate-pulse' : ''}`} />
                {statusInfo.label}
              </span>
            </div>
            <h2 className="truncate text-lg font-semibold tracking-[-0.03em] text-gray-950">{agentName}</h2>
            {messagePreview && (
              <p className="mt-1 max-w-3xl text-sm leading-6 text-gray-600">&ldquo;{messagePreview}&rdquo;</p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 md:justify-end">
          <TriggerSourceBadge source={triggerSource} detail={triggerDetail} size="md" className="bg-white/90" />
        </div>
      </div>

      <div className="grid gap-3 border-t border-[#efe6d8] px-5 py-4 sm:grid-cols-2 xl:grid-cols-4 xl:px-6">
        <div className="rounded-[1.2rem] border border-[#e6dccf] bg-[#fcfaf5] px-4 py-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9a7a5e]">
            <Clock className="h-3.5 w-3.5 text-[#8c6b4d]" />
            Runtime
          </div>
          <p className="mt-2 font-mono text-lg font-semibold text-gray-950">{elapsed}</p>
        </div>
        <div className="rounded-[1.2rem] border border-[#e6dccf] bg-[#fcfaf5] px-4 py-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9a7a5e]">
            <Wrench className="h-3.5 w-3.5 text-[#8c6b4d]" />
            Tools
          </div>
          <p className="mt-2 text-lg font-semibold text-gray-950">{toolCount}</p>
        </div>
        <div className="rounded-[1.2rem] border border-[#e6dccf] bg-[#fcfaf5] px-4 py-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9a7a5e]">
            <BarChart3 className="h-3.5 w-3.5 text-[#8c6b4d]" />
            Tokens
          </div>
          <p className="mt-2 text-lg font-semibold text-gray-950">{tokens.toLocaleString()}</p>
        </div>
        {cost > 0 && (
          <div className="rounded-[1.2rem] border border-[#e6dccf] bg-[#fcfaf5] px-4 py-3">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9a7a5e]">
              <DollarSign className="h-3.5 w-3.5 text-[#8c6b4d]" />
              Cost
            </div>
            <p className="mt-2 text-lg font-semibold text-gray-950">${cost.toFixed(4)}</p>
          </div>
        )}
      </div>
    </div>
  )
}
