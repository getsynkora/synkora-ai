'use client'

import { useState, useEffect } from 'react'
import { extractErrorMessage } from '@/lib/api/error'
import { cn } from '@/lib/utils/cn'
import type { AutopilotStatus } from '@/lib/api/knowledge-autopilot'
import { getAutopilotStatus, triggerCompilation } from '@/lib/api/knowledge-autopilot'

interface CompilationStatusProps {
  kbId: string
}

export function CompilationStatus({ kbId }: CompilationStatusProps) {
  const [status, setStatus] = useState<AutopilotStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [compiling, setCompiling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadStatus()
  }, [kbId])

  const loadStatus = async () => {
    try {
      const data = await getAutopilotStatus(kbId)
      setStatus(data)
    } catch {
      // Status load failure is non-critical
    } finally {
      setLoading(false)
    }
  }

  const handleCompile = async () => {
    setCompiling(true)
    setError(null)
    try {
      const result = await triggerCompilation(kbId)
      if (result?.status === 'failed') {
        setError(result.error || 'Compilation failed')
      }
      await loadStatus()
    } catch (err: any) {
      setError(extractErrorMessage(err, err?.message || 'Compilation failed'))
    } finally {
      setCompiling(false)
    }
  }

  if (loading) {
    return (
      <div className="bg-white border border-line shadow-sm rounded-xl p-5 motion-safe:animate-pulse">
        <div className="h-3 w-24 bg-sand rounded mb-4" />
        <div className="h-8 w-16 bg-sand rounded mb-3" />
        <div className="h-3 w-32 bg-sand rounded" />
      </div>
    )
  }

  if (!status) return null

  const healthPct = ((1 - status.avg_staleness) * 100).toFixed(0)
  const healthColor =
    status.avg_staleness < 0.3 ? 'text-leaf' :
    status.avg_staleness < 0.6 ? 'text-warn' : 'text-primary-500'
  const healthBarColor =
    status.avg_staleness < 0.3 ? 'bg-leaf' :
    status.avg_staleness < 0.6 ? 'bg-warn' : 'bg-primary-500'

  return (
    <div className="bg-white border border-line shadow-sm rounded-xl p-5 space-y-4">
      {/* Health score */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-extrabold text-ash">Knowledge Health</span>
          <span className={cn('text-sm font-extrabold', healthColor)}>{healthPct}%</span>
        </div>
        <div className="h-2 bg-sand rounded-full overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-700', healthBarColor)}
            style={{ width: `${healthPct}%` }}
          />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-[10px] font-bold text-ash">Articles</p>
          <p className="text-2xl font-extrabold text-ink tracking-tight">{status.total_articles}</p>
        </div>
        <div>
          <p className="text-[10px] font-bold text-ash">Categories</p>
          <p className="text-2xl font-extrabold text-ink tracking-tight">{Object.keys(status.category_counts).length}</p>
        </div>
      </div>

      {/* Last compilation */}
      {status.last_compilation && (
        <div className="text-xs space-y-2 pt-3 border-t border-sand">
          <div className="flex justify-between">
            <span className="font-medium text-ash">Last compiled</span>
            <span className="font-bold text-ink-soft">
              {status.last_compilation.completed_at
                ? new Date(status.last_compilation.completed_at).toLocaleDateString()
                : 'In progress'}
            </span>
          </div>
          {status.last_compilation.status && (
            <div className="flex justify-between">
              <span className="font-medium text-ash">Status</span>
              <span className={cn(
                'capitalize font-bold',
                status.last_compilation.status === 'completed' ? 'text-leaf' :
                status.last_compilation.status === 'failed' ? 'text-primary-500' : 'text-warn',
              )}>
                {status.last_compilation.status}
              </span>
            </div>
          )}
          {(status.last_compilation.articles_created > 0 || status.last_compilation.articles_updated > 0) && (
            <div className="flex justify-between">
              <span className="font-medium text-ash">Changes</span>
              <span className="font-bold text-ink-soft">
                +{status.last_compilation.articles_created} new, ~{status.last_compilation.articles_updated} updated
              </span>
            </div>
          )}
        </div>
      )}

      {/* Compile error */}
      {error && (
        <div className="text-xs font-medium text-primary-700 bg-primary-50 border border-primary-200 rounded-xl px-3 py-2.5">
          {error}
        </div>
      )}

      {/* Compile button */}
      <button
        onClick={handleCompile}
        disabled={compiling}
        className="w-full px-3 py-2.5 bg-ink hover:bg-ink/85 text-white text-sm font-bold rounded-xl hover:from-primary-600 hover:to-primary-700 transition-[color,background-color,border-color,box-shadow,opacity,transform] shadow-sm shadow-primary-500/20 disabled:opacity-50"
      >
        {compiling ? (
          <span className="flex items-center justify-center gap-2">
            <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full motion-safe:animate-spin" />
            Compiling...
          </span>
        ) : (
          'Recompile Wiki'
        )}
      </button>
    </div>
  )
}
