'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Sparkles, Zap } from 'lucide-react'
import { LifeAuditForm } from '@/components/rate-my-life/LifeAuditForm'
import { createLifeAudit, listLifeAudits } from '@/lib/api/rate-my-life'
import type { DimensionAnswer, LifeAuditResult } from '@/lib/api/rate-my-life'
import DashboardPageShell, { DashboardPagePanel } from '@/components/dashboard/DashboardPageShell'

export default function RateMyLifePage() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [history, setHistory] = useState<LifeAuditResult[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listLifeAudits()
      .then((res) => setHistory(res.audits || []))
      .catch(() => {})
  }, [])

  const handleSubmit = async (answers: DimensionAnswer[]) => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await createLifeAudit(answers)
      router.push(`/rate-my-life/${result.id}`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create life audit'
      setError(msg)
      setIsLoading(false)
    }
  }

  return (
    <DashboardPageShell
      title="Rate My Life"
      description="Answer 6 quick questions, then watch 5 specialist AI agents debate your scores in real time and produce a shareable life scorecard."
      icon={Sparkles}
      badge="Labs"
      maxWidthClassName="max-w-5xl"
      breadcrumbs={[
        { label: 'Home', href: '/' },
        { label: 'Rate My Life' },
      ]}
      stats={[
        { label: 'Past Audits', value: history.length },
        { label: 'Flow', value: '6 questions' },
      ]}
    >
      {error ? (
        <DashboardPagePanel className="mb-6 border-[#eed6dd] bg-[linear-gradient(180deg,_rgba(252,245,247,0.98),_rgba(249,236,240,0.96))] p-4 text-sm text-[#8a445c]">
          {error}
        </DashboardPagePanel>
      ) : null}

      <DashboardPagePanel className="mb-10 p-6 sm:p-8">
        <LifeAuditForm onSubmit={handleSubmit} isLoading={isLoading} />
      </DashboardPagePanel>

      {history.length > 0 ? (
        <div>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.2em] text-[#9a7a5e]">Past Audits</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {history.map((audit) => (
              <DashboardPagePanel
                key={audit.id}
                className="cursor-pointer p-4 transition-all hover:-translate-y-0.5 hover:border-[#d4baa1]"
              >
                <button
                  onClick={() => router.push(`/rate-my-life/${audit.id}`)}
                  className="w-full text-left"
                >
                  <div className="mb-3 flex items-center justify-between">
                    <span
                      className="text-2xl font-semibold tabular-nums"
                      style={{ color: audit.scores.overall < 4 ? '#d65563' : audit.scores.overall <= 6 ? '#b7822d' : '#2b7a52' }}
                    >
                      {audit.scores.overall}
                    </span>
                    <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${
                      audit.status === 'completed'
                        ? 'bg-[#ebf5ee] text-[#24543b]'
                        : audit.status === 'active'
                          ? 'bg-[#eef4fb] text-[#345c8a]'
                          : 'bg-[#f3ede5] text-[#6b5a4a]'
                    }`}>
                      {audit.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400">
                    {new Date(audit.created_at).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </p>
                </button>
              </DashboardPagePanel>
            ))}
          </div>
        </div>
      ) : null}
    </DashboardPageShell>
  )
}
