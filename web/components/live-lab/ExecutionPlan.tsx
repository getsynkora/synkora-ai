'use client'

import { cn } from '@/lib/utils/cn'
import type { ExecutionEvent } from '@/lib/api/live-lab'

interface ExecutionPlanProps {
  events: ExecutionEvent[]
  activeTools: string[]
  isLive: boolean
}

interface PlanStep {
  name: string
  displayName: string
  status: 'completed' | 'active' | 'pending'
  durationMs?: number
  description?: string
}

function buildPlanSteps(events: ExecutionEvent[], activeTools: string[]): PlanStep[] {
  const steps: PlanStep[] = []
  const seen = new Set<string>()

  for (const event of events) {
    if (event.type !== 'tool_status' || !event.tool_name) continue
    const name = event.tool_name
    if (seen.has(name) && event.status !== 'completed') continue

    const displayName = name.replace('internal_', '').replace(/_/g, ' ')

    if (event.status === 'started' && !seen.has(name)) {
      seen.add(name)
      steps.push({
        name,
        displayName,
        status: 'active',
        description: event.description,
      })
    }

    if (event.status === 'completed' || event.status === 'error') {
      const existing = steps.find((s) => s.name === name)
      if (existing) {
        existing.status = 'completed'
        existing.durationMs = event.duration_ms
      } else {
        seen.add(name)
        steps.push({
          name,
          displayName,
          status: 'completed',
          durationMs: event.duration_ms,
          description: event.description,
        })
      }
    }
  }

  // Mark currently active tools
  for (const tool of activeTools) {
    const step = steps.find((s) => s.name === tool)
    if (step) step.status = 'active'
  }

  return steps
}

export function ExecutionPlan({ events, activeTools, isLive }: ExecutionPlanProps) {
  const steps = buildPlanSteps(events, activeTools)

  return (
    <div className="flex h-full flex-col bg-transparent">
      <div className="border-b border-sand-deep bg-paper px-4 py-3">
        <h3 className="text-[11px] font-semibold text-clay">Execution Plan</h3>
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-3">
        {steps.length === 0 && (
          <div className="flex h-full items-center justify-center px-4 py-10">
            <p className="rounded-[1rem] border border-dashed border-line bg-white/80 px-4 py-3 text-center text-xs font-medium text-clay">
              {isLive ? 'Steps will appear as tools are used…' : 'No tools were used'}
            </p>
          </div>
        )}
        <div className="space-y-2">
          {steps.map((step, i) => (
            <div key={`${step.name}-${i}`} className="relative rounded-[1rem] border border-sand-deep bg-white/82 px-3 py-3">
              <div className="flex items-start gap-2.5">
                <div className="mt-0.5 flex-shrink-0">
                  {step.status === 'completed' && (
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-leaf-wash">
                      <svg aria-hidden="true" className="h-3.5 w-3.5 text-leaf" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  )}
                  {step.status === 'active' && (
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-sand">
                      <div className="h-2.5 w-2.5 rounded-full bg-warn motion-safe:animate-pulse" />
                    </div>
                  )}
                  {step.status === 'pending' && (
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-paper">
                      <div className="h-1.5 w-1.5 rounded-full bg-taupe" />
                    </div>
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <p
                    className={cn(
                      'text-[13px] font-semibold capitalize',
                      step.status === 'completed' && 'text-ink',
                      step.status === 'active' && 'text-ink',
                      step.status === 'pending' && 'text-ash',
                    )}
                  >
                    {step.displayName}
                  </p>
                  {step.description ? (
                    <p className="mt-1 text-xs leading-5 text-ink-mute">{step.description}</p>
                  ) : null}
                  {step.durationMs !== undefined && (
                    <p className="mt-2 font-mono text-[10px] text-clay">{step.durationMs}ms</p>
                  )}
                </div>
              </div>

              {i < steps.length - 1 && (
                <div className="absolute bottom-[-9px] left-6 h-2.5 w-px bg-line" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
