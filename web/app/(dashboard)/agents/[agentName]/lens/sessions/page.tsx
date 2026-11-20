'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Activity, ChevronLeft, ChevronRight } from 'lucide-react'
import {
  getLensSessions,
  type LensSessionRow,
  type LensRange,
} from '@/lib/api/agent-lens'
import AgentPageShell, { AgentPagePanel } from '@/components/agents/AgentPageShell'

const RANGE_OPTIONS: { label: string; value: LensRange }[] = [
  { label: '24h', value: '24h' },
  { label: '7d', value: '7d' },
  { label: '30d', value: '30d' },
  { label: '90d', value: '90d' },
]

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function formatCost(n: number): string {
  if (n === 0) return '$0.00'
  if (n < 0.001) return `$${n.toFixed(6)}`
  return `$${n.toFixed(4)}`
}

function StatusBadge({ status }: { status: string }) {
  const styles =
    status === 'ACTIVE' ? 'bg-leaf-wash text-forest' :
    status === 'ARCHIVED' ? 'bg-sand text-ink-soft' :
    'bg-blush-wash text-leaf'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${styles}`}>
      {status}
    </span>
  )
}

function formatDate(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
}

export default function LensSessionsPage() {
  const params = useParams()
  const agentSlug = params.agentName as string
  const router = useRouter()

  const [range, setRange] = useState<LensRange>('7d')
  const [page, setPage] = useState(1)
  const [sessions, setSessions] = useState<LensSessionRow[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const pageSize = 20

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getLensSessions(agentSlug, range, page, pageSize)
      setSessions(data.sessions)
      setTotal(data.total)
      setTotalPages(data.total_pages)
    } catch (e: any) {
      setError(e?.message || 'Failed to load sessions')
    } finally {
      setLoading(false)
    }
  }, [agentSlug, range, page])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    setPage(1)
  }, [range])

  return (
    <AgentPageShell
      agentName={agentSlug}
      title="Lens Sessions"
      description="Browse and inspect captured sessions for this agent."
      icon={Activity}
      badge="Analytics"
      maxWidthClassName="max-w-[88rem]"
      actions={
        <div className="rounded-[1.1rem] border border-black/10 bg-white/80 p-1.5 shadow-soft">
          <div className="flex flex-wrap gap-1.5">
            {RANGE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setRange(opt.value)}
                className={`rounded-[0.9rem] px-3.5 py-2 text-sm font-semibold transition-colors ${
                  range === opt.value
                    ? 'bg-ink text-white'
                    : 'text-ink-soft hover:bg-paper hover:text-ink'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      }
    >
      {error ? (
        <AgentPagePanel className="mb-6 border-blush-wash bg-white p-4">
          <p className="text-sm text-wine">{error}</p>
        </AgentPagePanel>
      ) : null}

      <AgentPagePanel className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-sand-deep text-sm">
          <thead className="bg-cream">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">Session</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">Model</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">Tokens</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">Cost</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">Messages</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">Date</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-ink-mute">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-sand">
            {loading ? (
              <tr>
                <td colSpan={7} className="text-center py-16 text-ash">Loading…</td>
              </tr>
            ) : sessions.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-16 text-ash">No sessions found for this period</td>
              </tr>
            ) : (
              sessions.map(s => (
                <tr
                  key={s.id}
                  onClick={() => router.push(`/agents/${agentSlug}/lens/sessions/${s.id}`)}
                  className="hover:bg-cream cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3">
                    <span className="font-medium text-ink truncate max-w-xs block">{s.name}</span>
                  </td>
                  <td className="px-4 py-3 text-ink-mute text-xs">{s.model_name || '-'}</td>
                  <td className="px-4 py-3 text-right text-ink-soft">{formatTokens(s.total_tokens)}</td>
                  <td className="px-4 py-3 text-right text-ink-soft">{formatCost(s.cost_usd)}</td>
                  <td className="px-4 py-3 text-right text-ink-soft">{s.message_count}</td>
                  <td className="px-4 py-3 text-ink-mute text-xs">{formatDate(s.created_at)}</td>
                  <td className="px-4 py-3 text-center">
                    <StatusBadge status={s.status} />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        </div>
      </AgentPagePanel>

      {!loading && totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-xs text-ink-mute">{total} sessions total</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-1.5 rounded-lg border border-line text-ink-mute disabled:opacity-40 hover:bg-cream transition-colors"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-sm text-ink-soft">
              Page {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-1.5 rounded-lg border border-line text-ink-mute disabled:opacity-40 hover:bg-cream transition-colors"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </AgentPageShell>
  )
}
