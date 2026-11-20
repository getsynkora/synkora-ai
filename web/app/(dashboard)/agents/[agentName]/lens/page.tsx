'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft, Activity, Bell, Plus, Trash2, CheckCircle, XCircle,
  AlertTriangle, Wrench, Zap, DollarSign, Clock, TrendingUp, BarChart2,
  ThumbsUp, ThumbsDown, Minus, Scissors, Database, Star, FlaskConical,
  Play, ChevronDown, ChevronRight,
} from 'lucide-react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from 'recharts'
import {
  getLensOverview,
  getLensTokenDistribution,
  getLensAlerts,
  getLensToolAnalytics,
  getLensToolROI,
  getLensCompaction,
  getLensCache,
  getLensQuality,
  getLensEvalHistory,
  createLensAlert,
  deleteLensAlert,
  type LensOverviewResponse,
  type LensTokenDistributionResponse,
  type LensToolAnalyticsResponse,
  type LensToolROIResponse,
  type LensToolROIStat,
  type LensCompactionAnalyticsResponse,
  type LensCacheAnalyticsResponse,
  type LensQualityResponse,
  type LensEvalHistoryResponse,
  type LensEvalRunRow,
  type AlertResponse,
  type AlertCreateBody,
  type LensRange,
} from '@/lib/api/agent-lens'
import {
  listDatasets,
  createDataset,
  deleteDataset,
  listCases,
  createCase,
  deleteCase,
  triggerEvalRun,
  getRunResults,
  type EvalDataset,
  type EvalCase,
  type EvalResult,
} from '@/lib/api/eval'
import AgentPageShell, { AgentPagePanel, AgentPageTabs } from '@/components/agents/AgentPageShell'

type Tab = 'overview' | 'tools' | 'roi' | 'compaction' | 'cache' | 'alerts' | 'quality' | 'eval'

const RANGE_OPTIONS: { label: string; value: LensRange }[] = [
  { label: '24h', value: '24h' },
  { label: '7d', value: '7d' },
  { label: '30d', value: '30d' },
  { label: '90d', value: '90d' },
]

const CHART_COLORS = ['#e11d48', '#8b5cf6', '#f43f5e', '#a78bfa', '#fb7185', '#c4b5fd']

// ─── Formatters ──────────────────────────────────────────────────────────────

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function fmtCost(n: number): string {
  if (n === 0) return '$0.00'
  if (n < 0.01) return `$${n.toFixed(5)}`
  return `$${n.toFixed(4)}`
}

function fmtLatency(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms}ms`
}

function fmtPct(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`
}

// ─── Small components ─────────────────────────────────────────────────────────

function KpiCard({
  label, value, sub, icon: Icon, iconColor, iconBg,
}: {
  label: string
  value: string
  sub?: string
  icon: React.ElementType
  iconColor: string
  iconBg: string
}) {
  return (
    <div className="rounded-xl border border-line bg-white p-5 flex items-start gap-3 shadow-sm">
      <div className={`rounded-full p-2.5 shrink-0 ${iconBg}`}>
        <Icon className={`h-4 w-4 ${iconColor}`} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-ink-mute mb-0.5">{label}</p>
        <p className="text-3xl font-bold text-ink leading-none">{value}</p>
        {sub && <p className="text-xs text-ash mt-1">{sub}</p>}
      </div>
    </div>
  )
}

function SuccessRateBar({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100)
  const color = pct >= 95 ? 'bg-primary-500' : pct >= 80 ? 'bg-warn' : 'bg-ink'
  const textColor = pct >= 95 ? 'text-primary-600' : pct >= 80 ? 'text-gold' : 'text-danger'
  const bg = pct >= 95 ? 'bg-primary-50 border-primary-200' : pct >= 80 ? 'bg-sand-deep border-honey' : 'bg-blush-wash border-blush'
  return (
    <div className={`rounded-xl border p-5 shadow-sm ${bg}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-ink-mute">Tool Success Rate</span>
        <span className={`text-3xl font-bold ${textColor}`}>{pct}%</span>
      </div>
      <div className="h-1.5 bg-line rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-[color,background-color,border-color,box-shadow,opacity,transform] ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function DonutCard({
  title, data, colors, totalLabel, totalValue, legendFormatter,
}: {
  title: string
  data: { name: string; value: number }[]
  colors: string[]
  totalLabel: string
  totalValue: string
  legendFormatter: (item: { name: string; value: number }) => string
}) {
  const total = data.reduce((s, d) => s + d.value, 0)
  return (
    <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-ink mb-3">{title}</h3>
      {total > 0 ? (
        <>
          <div className="relative">
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={data}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  dataKey="value"
                  paddingAngle={2}
                >
                  {data.map((_, i) => (
                    <Cell key={i} fill={colors[i % colors.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: number) => [legendFormatter({ name: '', value: v }), '']}
                  contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12 }}
                />
              </PieChart>
            </ResponsiveContainer>
            {/* Center label */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="text-base font-bold text-ink">{totalValue}</span>
              <span className="text-xs text-ash">{totalLabel}</span>
            </div>
          </div>
          {/* Legend table */}
          <div className="space-y-1.5 mt-2">
            {data.slice(0, 6).map((item, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-sm shrink-0"
                    style={{ backgroundColor: colors[i % colors.length] }}
                  />
                  <span className="text-ink-soft truncate">{item.name}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0 ml-2">
                  <span className="text-ink font-medium">{legendFormatter(item)}</span>
                  <span className="text-ash w-10 text-right">
                    {total > 0 ? `${Math.round((item.value / total) * 100)}%` : '0%'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="flex items-center justify-center h-40 text-ash text-sm">No data yet</div>
      )}
    </div>
  )
}

// ─── Compaction ───────────────────────────────────────────────────────────────

function CompactionView({ data }: { data: LensCompactionAnalyticsResponse }) {
  const pruningPct = Math.round(data.pruning_rate * 100)
  const ratiosPct = Math.round(data.avg_pruning_ratio * 100)
  const hasDataWarning = data.data_bearing_pruned_total > 0
  const trendData = data.trend.map(t => ({
    date: t.date.slice(5),  // MM-DD
    events: t.pruning_events,
    tokens: t.tokens_saved,
    data_bearing: t.data_bearing_pruned,
  }))

  return (
    <div className="space-y-6">
      {/* Quality warning */}
      {hasDataWarning && (
        <div className="rounded-lg border border-honey bg-sand-deep px-4 py-3 text-sm text-gold">
          <span className="font-semibold">Quality risk: </span>
          {data.data_bearing_pruned_total} data-bearing tool results (SQL rows, file contents) were
          trimmed during context compaction. This can cause the LLM to lose track of data it already
          retrieved. Consider reducing tool output sizes or increasing context limits.
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard
          label="Sessions Compacted"
          value={`${pruningPct}%`}
          sub={`${data.sessions_with_pruning} of ${data.total_sessions}`}
          icon={Scissors}
          iconBg={pruningPct > 30 ? 'bg-sand-deep' : 'bg-primary-50'}
          iconColor={pruningPct > 30 ? 'text-warn' : 'text-primary-600'}
        />
        <KpiCard
          label="Tokens Saved"
          value={fmtTokens(data.total_tokens_saved)}
          sub={`avg ${fmtTokens(Math.round(data.avg_tokens_saved_per_session))} / session`}
          icon={TrendingUp}
          iconBg="bg-leaf-wash"
          iconColor="text-leaf"
        />
        <KpiCard
          label="Data Tools Trimmed"
          value={String(data.data_bearing_pruned_total)}
          sub="SQL/file results affected"
          icon={AlertTriangle}
          iconBg={hasDataWarning ? 'bg-sand-deep' : 'bg-cream'}
          iconColor={hasDataWarning ? 'text-warn' : 'text-ash'}
        />
        <KpiCard
          label="Avg Pruning Ratio"
          value={`${ratiosPct}%`}
          sub={`${data.total_results_pruned} of ${data.total_results_evaluated} results`}
          icon={BarChart2}
          iconBg="bg-blush-wash"
          iconColor="text-plum"
        />
      </div>

      {/* Trend chart */}
      {trendData.length > 0 && (
        <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-ink-soft mb-4">Pruning Events Over Time</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={trendData} margin={{ top: 0, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12 }}
              />
              <Line type="monotone" dataKey="events" stroke="#e11d48" strokeWidth={2} dot={false} name="Pruning events" />
              <Line type="monotone" dataKey="data_bearing" stroke="#f59e0b" strokeWidth={2} dot={false} name="Data tools trimmed" strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
          <div className="mt-2 flex items-center gap-4 text-xs text-ink-mute">
            <span className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-5 bg-ink" />Pruning events</span>
            <span className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-5 bg-warn" />Data tools trimmed</span>
          </div>
        </div>
      )}

      {/* Explanation */}
      <div className="rounded-lg border border-sand bg-cream px-4 py-3 text-xs text-ink-mute leading-relaxed">
        <span className="font-medium text-ink-soft">How compaction works: </span>
        When a conversation grows too long, older tool results are compacted to free context space.
        Non-data tools (e.g. send_email) get a 1-line summary. Data-bearing tools (SQL queries, CSV reads) are
        trimmed with head+tail preservation to keep data rows intact, but heavy trimming can still degrade quality.
        The <span className="font-medium text-gold">Data Tools Trimmed</span> counter shows how often this
        quality-sensitive path was triggered.
      </div>
    </div>
  )
}

// ─── Cache ─────────────────────────────────────────────────────────────────────

function CacheView({ data }: { data: LensCacheAnalyticsResponse }) {
  const hitPct = Math.round(data.cache_hit_rate * 100)
  const avgCtxPct = Math.round(data.avg_context_utilization_pct)
  const maxCtxPct = Math.round(data.max_context_utilization_pct)
  const highPressurePct = data.total_llm_calls > 0
    ? Math.round((data.high_pressure_calls / data.total_llm_calls) * 100)
    : 0
  const trendData = data.trend.map(t => ({
    date: t.date.slice(5),
    hit_rate: Math.round(t.cache_hit_rate * 100),
    cache_read: t.cache_read_tokens,
    cache_creation: t.cache_creation_tokens,
  }))

  const ctxColor = avgCtxPct >= 80 ? 'text-leaf' : avgCtxPct >= 60 ? 'text-gold' : 'text-forest'
  const ctxBg = avgCtxPct >= 80 ? 'bg-blush-wash border-blush' : avgCtxPct >= 60 ? 'bg-sand-deep border-honey' : 'bg-leaf-wash border-mint'

  return (
    <div className="space-y-6">
      {/* Context pressure warning */}
      {data.high_pressure_calls > 0 && (
        <div className={`rounded-lg border px-4 py-3 text-sm ${avgCtxPct >= 80 ? 'border-blush bg-blush-wash text-wine' : 'border-honey bg-sand-deep text-gold'}`}>
          <span className="font-semibold">Context pressure: </span>
          {data.high_pressure_calls} LLM calls ({highPressurePct}%) used ≥80% of the context window.
          {avgCtxPct >= 70 && ' Consider reducing system prompt size or enabling more aggressive compaction.'}
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard
          label="Cache Hit Rate"
          value={`${hitPct}%`}
          sub={`${data.total_llm_calls} LLM calls`}
          icon={Database}
          iconBg={hitPct >= 50 ? 'bg-leaf-wash' : 'bg-cream'}
          iconColor={hitPct >= 50 ? 'text-leaf' : 'text-ash'}
        />
        <KpiCard
          label="Est. Savings"
          value={fmtCost(data.estimated_savings_usd)}
          sub="from cache reads"
          icon={DollarSign}
          iconBg="bg-leaf-wash"
          iconColor="text-leaf"
        />
        <KpiCard
          label="Avg Context Use"
          value={`${avgCtxPct}%`}
          sub={`max ${maxCtxPct}%`}
          icon={TrendingUp}
          iconBg={avgCtxPct >= 80 ? 'bg-blush-wash' : avgCtxPct >= 60 ? 'bg-sand-deep' : 'bg-leaf-wash'}
          iconColor={avgCtxPct >= 80 ? 'text-danger' : avgCtxPct >= 60 ? 'text-warn' : 'text-leaf'}
        />
        <KpiCard
          label="High Pressure Calls"
          value={String(data.high_pressure_calls)}
          sub="≥80% context used"
          icon={AlertTriangle}
          iconBg={data.high_pressure_calls > 0 ? 'bg-sand-deep' : 'bg-cream'}
          iconColor={data.high_pressure_calls > 0 ? 'text-warn' : 'text-ash'}
        />
      </div>

      {/* Context utilization gauge */}
      <div className={`rounded-xl border p-5 shadow-sm ${ctxBg}`}>
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-medium text-ink-soft">Average Context Window Utilization</span>
          <span className={`text-3xl font-bold ${ctxColor}`}>{avgCtxPct}%</span>
        </div>
        <div className="h-2 bg-line rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-[color,background-color,border-color,box-shadow,opacity,transform] ${avgCtxPct >= 80 ? 'bg-ink' : avgCtxPct >= 60 ? 'bg-warn' : 'bg-leaf'}`}
            style={{ width: `${Math.min(avgCtxPct, 100)}%` }}
          />
        </div>
        <div className="mt-2 flex justify-between text-xs text-ash">
          <span>0%</span>
          <span className="text-warn font-medium">60% caution</span>
          <span className="text-danger font-medium">80% critical</span>
          <span>100%</span>
        </div>
      </div>

      {/* Token stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Total Input Tokens', value: fmtTokens(data.total_input_tokens), color: 'border-l-ash' },
          { label: 'Cache Read Tokens', value: fmtTokens(data.total_cache_read_tokens), color: 'border-l-leaf' },
          { label: 'Cache Creation Tokens', value: fmtTokens(data.total_cache_creation_tokens), color: 'border-l-plum' },
        ].map(item => (
          <div key={item.label} className={`rounded-xl border border-line bg-white p-4 shadow-sm border-l-4 ${item.color}`}>
            <p className="text-xs font-medium text-ink-mute mb-1">{item.label}</p>
            <p className="text-2xl font-bold text-ink">{item.value}</p>
          </div>
        ))}
      </div>

      {/* Trend chart */}
      {trendData.length > 0 && (
        <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-ink-soft mb-4">Cache Hit Rate Over Time</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={trendData} margin={{ top: 0, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} unit="%" domain={[0, 100]} />
              <Tooltip
                contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12 }}
                formatter={(v: number) => [`${v}%`, 'Cache hit rate']}
              />
              <Line type="monotone" dataKey="hit_rate" stroke="#10b981" strokeWidth={2} dot={false} name="Hit rate %" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Explanation */}
      <div className="rounded-lg border border-sand bg-cream px-4 py-3 text-xs text-ink-mute leading-relaxed">
        <span className="font-medium text-ink-soft">Prompt cache: </span>
        Anthropic's prompt caching stores common prefix tokens (system prompt, tools) server-side.
        Cache reads cost ~10% of normal input token price, saving cost on repeated calls.
        A high hit rate means the agent is reusing context efficiently.
        Context utilization tracks how much of the model's context window is used per call, sustained
        usage above 80% leads to compaction and potential quality degradation.
      </div>
    </div>
  )
}

// ─── Tool ROI ─────────────────────────────────────────────────────────────────

const VERDICT_CONFIG = {
  keep:    { label: 'Keep',              bg: 'bg-leaf-wash',  text: 'text-forest',  border: 'border-mint',  Icon: ThumbsUp },
  review:  { label: 'Review',            bg: 'bg-sand-deep',  text: 'text-gold',  border: 'border-honey',  Icon: AlertTriangle },
  remove:  { label: 'May be unnecessary', bg: 'bg-blush-wash',  text: 'text-danger',    border: 'border-blush',    Icon: ThumbsDown },
  neutral: { label: 'Insufficient data', bg: 'bg-sand',  text: 'text-ink-mute',   border: 'border-line',   Icon: Minus },
} as const

function LiftBadge({ lift }: { lift: number }) {
  const pct = (lift * 100).toFixed(1)
  if (Math.abs(lift) < 0.01) return <span className="text-ash text-xs">—</span>
  return lift > 0
    ? <span className="text-forest font-semibold text-sm">+{pct}%</span>
    : <span className="text-leaf font-semibold text-sm">{pct}%</span>
}

function CostImpactBadge({ pct }: { pct: number }) {
  const label = `${pct >= 0 ? '+' : ''}${(pct * 100).toFixed(1)}%`
  if (Math.abs(pct) < 0.005) return <span className="text-ash text-xs">—</span>
  return <span className={`text-xs font-medium ${pct > 0.1 ? 'text-warn' : pct < -0.05 ? 'text-leaf' : 'text-ink-soft'}`}>{label}</span>
}

function ToolROIView({ data }: { data: LensToolROIResponse }) {
  const tools = data.tools
  const keeps   = tools.filter(t => t.verdict === 'keep').length
  const reviews = tools.filter(t => t.verdict === 'review').length
  const removes = tools.filter(t => t.verdict === 'remove').length

  // Smart insight sentence
  const topRemoval = tools.find(t => t.verdict === 'remove')
  const worstReview = tools.filter(t => t.verdict === 'review').sort((a, b) => a.completion_lift - b.completion_lift)[0]
  const insight = topRemoval
    ? `Consider removing ${topRemoval.tool_name}, sessions using it resolve ${Math.abs(topRemoval.completion_lift * 100).toFixed(0)}% less often than sessions without it.`
    : worstReview
    ? `${worstReview.tool_name} is called ${worstReview.calls_per_session.toFixed(1)}×/session but shows only ${(worstReview.completion_lift * 100).toFixed(1)}% completion lift, worth reviewing.`
    : keeps > 0
    ? `All ${keeps} tracked tool${keeps > 1 ? 's are' : ' is'} contributing positively to session resolution.`
    : null

  return (
    <div>
      {/* Summary bar */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cream border border-line text-sm text-ink-soft">
          <BarChart2 size={14} className="text-ash" />
          <span className="font-medium">{tools.length}</span> tools, <span className="font-medium">{data.total_sessions}</span> sessions analyzed
        </div>
        {keeps > 0 && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-leaf-wash border border-mint text-sm text-forest">
            <ThumbsUp size={13} /><span className="font-medium">{keeps}</span> helping
          </div>
        )}
        {reviews > 0 && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sand-deep border border-honey text-sm text-gold">
            <AlertTriangle size={13} /><span className="font-medium">{reviews}</span> need review
          </div>
        )}
        {removes > 0 && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blush-wash border border-blush text-sm text-danger">
            <ThumbsDown size={13} /><span className="font-medium">{removes}</span> may be unnecessary
          </div>
        )}
      </div>

      {/* Smart insight */}
      {insight && (
        <div className="mb-5 rounded-lg border border-primary-200 bg-primary-50 px-4 py-3 text-sm text-primary-800">
          <span className="font-semibold">Insight: </span>{insight}
        </div>
      )}

      {tools.length === 0 ? (
        <div className="rounded-xl border border-line bg-white p-12 text-center text-ash text-sm shadow-sm">
          No tool call data in this period. ROI analysis requires tool calls to be recorded.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-white shadow-sm">
          <table className="min-w-full divide-y divide-sand text-sm">
            <thead className="bg-cream">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">Tool</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">Calls / Session</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">Error %</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">
                  Completion Lift
                  <span className="block text-ash font-normal normal-case text-[10px]">sessions with vs without</span>
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">
                  Cost Impact
                  <span className="block text-ash font-normal normal-case text-[10px]">vs sessions without</span>
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">Sessions With</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-ink-mute">Verdict</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sand">
              {tools.map(tool => {
                const vc = VERDICT_CONFIG[tool.verdict as keyof typeof VERDICT_CONFIG] ?? VERDICT_CONFIG.neutral
                const VIcon = vc.Icon
                const errorPct = Math.round(tool.error_rate * 100)
                const errorColor = errorPct > 15 ? 'text-danger font-semibold' : errorPct > 5 ? 'text-warn' : 'text-ink-mute'
                return (
                  <tr key={tool.tool_name} className="hover:bg-cream">
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-ink">{tool.tool_name}</span>
                      <div className="text-[10px] text-ash mt-0.5">{tool.total_calls.toLocaleString()} total calls</div>
                    </td>
                    <td className="px-4 py-3 text-right text-ink-soft font-medium">{tool.calls_per_session.toFixed(1)}</td>
                    <td className={`px-4 py-3 text-right ${errorColor}`}>{errorPct}%</td>
                    <td className="px-4 py-3 text-right">
                      <LiftBadge lift={tool.completion_lift} />
                      <div className="text-[10px] text-ash mt-0.5">
                        {Math.round(tool.completion_rate_with * 100)}% with, {Math.round(tool.completion_rate_without * 100)}% without
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <CostImpactBadge pct={tool.cost_impact_pct} />
                      <div className="text-[10px] text-ash mt-0.5">
                        ${tool.avg_cost_with.toFixed(4)} vs ${tool.avg_cost_without.toFixed(4)}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right text-ink-soft">
                      {tool.sessions_with.toLocaleString()}
                      <div className="text-[10px] text-ash">{tool.sessions_without} without</div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border ${vc.bg} ${vc.text} ${vc.border}`}>
                        <VIcon size={11} />
                        {vc.label}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Explanation footer */}
      <div className="mt-4 rounded-lg border border-sand bg-cream px-4 py-3 text-xs text-ink-mute leading-relaxed">
        <span className="font-medium text-ink-soft">How verdicts are assigned: </span>
        <span className="font-medium text-forest">Keep</span> = tool clearly improves session resolution rate (&gt;5% lift).
        {' '}<span className="font-medium text-gold">Review</span> = negative lift or high error rate, may be hurting more than helping.
        {' '}<span className="font-medium text-danger">May be unnecessary</span> = sessions with this tool resolve significantly less often (&gt;15% worse) or fail &gt;50% of the time.
        {' '}Completion lift measures the difference in resolution rate between sessions that used the tool and sessions that did not.
        {' '}Requires 3+ sessions per tool for a verdict.
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function LensOverviewPage() {
  const params = useParams()
  const agentSlug = params.agentName as string

  const [tab, setTab] = useState<Tab>('overview')
  const [range, setRange] = useState<LensRange>('7d')

  const [overview, setOverview] = useState<LensOverviewResponse | null>(null)
  const [distribution, setDistribution] = useState<LensTokenDistributionResponse | null>(null)
  const [toolAnalytics, setToolAnalytics] = useState<LensToolAnalyticsResponse | null>(null)
  const [toolROI, setToolROI] = useState<LensToolROIResponse | null>(null)
  const [compaction, setCompaction] = useState<LensCompactionAnalyticsResponse | null>(null)
  const [cache, setCache] = useState<LensCacheAnalyticsResponse | null>(null)
  const [alerts, setAlerts] = useState<AlertResponse[]>([])
  const [quality, setQuality] = useState<LensQualityResponse | null>(null)
  const [evalHistory, setEvalHistory] = useState<LensEvalHistoryResponse | null>(null)

  // Eval dataset management
  const [datasets, setDatasets] = useState<EvalDataset[]>([])
  const [selectedDataset, setSelectedDataset] = useState<EvalDataset | null>(null)
  const [cases, setCases] = useState<EvalCase[]>([])
  const [expandedRun, setExpandedRun] = useState<string | null>(null)
  const [runResults, setRunResults] = useState<Record<string, EvalResult[]>>({})
  const [newDatasetName, setNewDatasetName] = useState('')
  const [newCaseInput, setNewCaseInput] = useState('')
  const [newCaseCriteria, setNewCaseCriteria] = useState('')
  const [datasetCreating, setDatasetCreating] = useState(false)
  const [caseAdding, setCaseAdding] = useState(false)
  const [runTriggering, setRunTriggering] = useState<string | null>(null)

  const [loading, setLoading] = useState(true)
  const [toolsLoading, setToolsLoading] = useState(false)
  const [roiLoading, setRoiLoading] = useState(false)
  const [compactionLoading, setCompactionLoading] = useState(false)
  const [cacheLoading, setCacheLoading] = useState(false)
  const [qualityLoading, setQualityLoading] = useState(false)
  const [evalLoading, setEvalLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [showAlertForm, setShowAlertForm] = useState(false)
  const [alertForm, setAlertForm] = useState<AlertCreateBody>({
    name: '',
    metric: 'failure_rate',
    condition: 'gt',
    threshold: 0.1,
    window_minutes: 60,
    notify_method: 'email',
  })
  const [alertSaving, setAlertSaving] = useState(false)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [ov, dist] = await Promise.all([
        getLensOverview(agentSlug, range),
        getLensTokenDistribution(agentSlug, range),
      ])
      setOverview(ov)
      setDistribution(dist)
    } catch (e: any) {
      setError(e?.message || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }, [agentSlug, range])

  const loadToolAnalytics = useCallback(async () => {
    setToolsLoading(true)
    try {
      const data = await getLensToolAnalytics(agentSlug, range)
      setToolAnalytics(data)
    } catch {
      // non-critical
    } finally {
      setToolsLoading(false)
    }
  }, [agentSlug, range])

  const loadROI = useCallback(async () => {
    setRoiLoading(true)
    try {
      setToolROI(await getLensToolROI(agentSlug, range))
    } catch { } finally { setRoiLoading(false) }
  }, [agentSlug, range])

  const loadCompaction = useCallback(async () => {
    setCompactionLoading(true)
    try {
      setCompaction(await getLensCompaction(agentSlug, range))
    } catch { } finally { setCompactionLoading(false) }
  }, [agentSlug, range])

  const loadCache = useCallback(async () => {
    setCacheLoading(true)
    try {
      setCache(await getLensCache(agentSlug, range))
    } catch { } finally { setCacheLoading(false) }
  }, [agentSlug, range])

  const loadAlerts = useCallback(async () => {
    try {
      setAlerts(await getLensAlerts(agentSlug))
    } catch { }
  }, [agentSlug])

  const loadQuality = useCallback(async () => {
    setQualityLoading(true)
    try {
      setQuality(await getLensQuality(agentSlug, range))
    } catch { } finally { setQualityLoading(false) }
  }, [agentSlug, range])

  const loadEval = useCallback(async () => {
    setEvalLoading(true)
    try {
      const [history, ds] = await Promise.all([
        getLensEvalHistory(agentSlug),
        listDatasets(agentSlug),
      ])
      setEvalHistory(history)
      setDatasets(ds.datasets)
    } catch { } finally { setEvalLoading(false) }
  }, [agentSlug])

  useEffect(() => { loadOverview() }, [loadOverview])
  useEffect(() => { if (tab === 'tools') loadToolAnalytics() }, [tab, loadToolAnalytics])
  useEffect(() => { if (tab === 'roi') loadROI() }, [tab, loadROI])
  useEffect(() => { if (tab === 'compaction') loadCompaction() }, [tab, loadCompaction])
  useEffect(() => { if (tab === 'cache') loadCache() }, [tab, loadCache])
  useEffect(() => { if (tab === 'alerts') loadAlerts() }, [tab, loadAlerts])
  useEffect(() => { if (tab === 'quality') loadQuality() }, [tab, loadQuality])
  useEffect(() => { if (tab === 'eval') loadEval() }, [tab, loadEval])

  async function handleCreateAlert() {
    setAlertSaving(true)
    try {
      await createLensAlert(agentSlug, alertForm)
      setShowAlertForm(false)
      setAlertForm({ name: '', metric: 'failure_rate', condition: 'gt', threshold: 0.1, window_minutes: 60, notify_method: 'email' })
      loadAlerts()
    } catch { } finally { setAlertSaving(false) }
  }

  async function handleDeleteAlert(id: string) {
    try {
      await deleteLensAlert(agentSlug, id)
      setAlerts(prev => prev.filter(a => a.id !== id))
    } catch { }
  }

  async function handleCreateDataset() {
    if (!newDatasetName.trim()) return
    setDatasetCreating(true)
    try {
      const ds = await createDataset(agentSlug, newDatasetName.trim())
      setDatasets(prev => [ds, ...prev])
      setNewDatasetName('')
    } catch { } finally { setDatasetCreating(false) }
  }

  async function handleDeleteDataset(datasetId: string) {
    try {
      await deleteDataset(agentSlug, datasetId)
      setDatasets(prev => prev.filter(d => d.dataset_id !== datasetId))
      if (selectedDataset?.dataset_id === datasetId) {
        setSelectedDataset(null)
        setCases([])
      }
    } catch { }
  }

  async function handleSelectDataset(ds: EvalDataset) {
    setSelectedDataset(ds)
    try {
      const res = await listCases(agentSlug, ds.dataset_id)
      setCases(res.cases)
    } catch { }
  }

  async function handleAddCase() {
    if (!selectedDataset || !newCaseInput.trim() || !newCaseCriteria.trim()) return
    setCaseAdding(true)
    try {
      const c = await createCase(agentSlug, selectedDataset.dataset_id, newCaseInput.trim(), newCaseCriteria.trim())
      setCases(prev => [...prev, c])
      setNewCaseInput('')
      setNewCaseCriteria('')
      setDatasets(prev => prev.map(d =>
        d.dataset_id === selectedDataset.dataset_id ? { ...d, case_count: d.case_count + 1 } : d
      ))
    } catch { } finally { setCaseAdding(false) }
  }

  async function handleDeleteCase(caseId: string) {
    if (!selectedDataset) return
    try {
      await deleteCase(agentSlug, selectedDataset.dataset_id, caseId)
      setCases(prev => prev.filter(c => c.case_id !== caseId))
      setDatasets(prev => prev.map(d =>
        d.dataset_id === selectedDataset.dataset_id ? { ...d, case_count: Math.max(0, d.case_count - 1) } : d
      ))
    } catch { }
  }

  async function handleTriggerRun(datasetId: string) {
    setRunTriggering(datasetId)
    try {
      await triggerEvalRun(agentSlug, datasetId)
      // Reload eval history after a brief delay to pick up the new run
      setTimeout(() => loadEval(), 1500)
    } catch { } finally { setRunTriggering(null) }
  }

  async function handleExpandRun(runId: string) {
    if (expandedRun === runId) {
      setExpandedRun(null)
      return
    }
    setExpandedRun(runId)
    if (!runResults[runId]) {
      try {
        const res = await getRunResults(agentSlug, runId)
        setRunResults(prev => ({ ...prev, [runId]: res.results }))
      } catch { }
    }
  }

  const stats = overview?.stats

  const byModelData = distribution?.by_model
    .filter(m => m.tokens > 0)
    .map(m => ({ name: m.model_name || 'unknown', value: m.tokens, cost: m.cost_usd })) ?? []

  const pvcData = distribution
    ? [
        { name: 'Prompt', value: distribution.prompt_vs_completion.input_tokens },
        { name: 'Completion', value: distribution.prompt_vs_completion.output_tokens },
      ].filter(d => d.value > 0)
    : []

  const toolBarData = (toolAnalytics?.tools ?? [])
    .slice(0, 10)
    .map(t => ({ name: t.tool_name, calls: t.total_calls, failures: t.failure_count }))

  return (
    <AgentPageShell
      agentName={agentSlug}
      title="Agent Lens"
      description="Usage analytics, tool performance, ROI, and alerting for this agent."
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
      <div className="space-y-6">
        <AgentPageTabs
          activeId={tab}
          onChange={(id) => setTab(id as Tab)}
          items={[
            { id: 'overview', label: 'Overview', icon: <Activity size={14} /> },
            { id: 'tools', label: 'Tools', icon: <Wrench size={14} /> },
            { id: 'roi', label: 'Tool ROI', icon: <BarChart2 size={14} /> },
            { id: 'compaction', label: 'Compaction', icon: <Scissors size={14} /> },
            { id: 'cache', label: 'Cache', icon: <Database size={14} /> },
            { id: 'alerts', label: 'Alerts', icon: <Bell size={14} /> },
            { id: 'quality', label: 'Quality', icon: <Star size={14} /> },
            { id: 'eval', label: 'Eval', icon: <FlaskConical size={14} /> },
          ]}
        />

        {error ? (
          <AgentPagePanel className="border-blush-wash bg-white p-4">
            <p className="text-sm text-wine">{error}</p>
          </AgentPagePanel>
        ) : null}

      {/* ── OVERVIEW TAB ───────────────────────────────────────────────────── */}
      {tab === 'overview' && (
        <>
          {loading ? (
            <div className="text-ash py-16 text-center">Loading…</div>
          ) : stats ? (
            <>
              {/* KPI cards */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
                <KpiCard
                  label="Sessions"
                  value={stats.total_sessions.toLocaleString()}
                  sub={`${range} period`}
                  icon={Activity}
                  iconBg="bg-primary-50"
                  iconColor="text-primary-600"
                />
                <KpiCard
                  label="LLM Requests"
                  value={stats.total_requests.toLocaleString()}
                  icon={Zap}
                  iconBg="bg-blush-wash"
                  iconColor="text-plum"
                />
                <KpiCard
                  label="Total Tokens"
                  value={fmtTokens(stats.total_tokens)}
                  sub={`${fmtTokens(stats.input_tokens)} in, ${fmtTokens(stats.output_tokens)} out`}
                  icon={TrendingUp}
                  iconBg="bg-blush-wash"
                  iconColor="text-plum"
                />
                <KpiCard
                  label="Total Cost"
                  value={fmtCost(stats.total_cost_usd)}
                  sub={`${fmtCost(stats.avg_cost_per_session)} / session`}
                  icon={DollarSign}
                  iconBg="bg-leaf-wash"
                  iconColor="text-leaf"
                />
                <KpiCard
                  label="Avg Latency"
                  value={fmtLatency(stats.avg_latency_ms)}
                  icon={Clock}
                  iconBg="bg-sand-deep"
                  iconColor="text-warn"
                />
                <KpiCard
                  label="Tool Calls"
                  value={stats.total_tool_calls.toLocaleString()}
                  sub={`${stats.failed_tool_calls} failed`}
                  icon={Wrench}
                  iconBg={stats.failed_tool_calls > 0 ? 'bg-blush-wash' : 'bg-primary-50'}
                  iconColor={stats.failed_tool_calls > 0 ? 'text-danger' : 'text-primary-600'}
                />
              </div>

              {/* Health + success rate */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
                <SuccessRateBar rate={stats.total_tool_calls > 0 ? 1 - stats.failure_rate : 1} />

                <div className="rounded-xl border border-line bg-white p-5 flex items-center gap-4 shadow-sm">
                  <div className="rounded-full bg-sand-deep p-3">
                    <AlertTriangle className="h-5 w-5 text-warn" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-ink-mute mb-0.5">Failed Calls</p>
                    <p className="text-3xl font-bold text-ink">{stats.failed_tool_calls}</p>
                    <p className="text-xs text-ash">of {stats.total_tool_calls} total</p>
                  </div>
                </div>

                <div className="rounded-xl border border-line bg-white p-5 flex items-center gap-4 shadow-sm">
                  <div className="rounded-full bg-leaf-wash p-3">
                    <Clock className="h-5 w-5 text-leaf" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-ink-mute mb-0.5">Avg Tool Duration</p>
                    <p className="text-3xl font-bold text-ink">{fmtLatency(stats.avg_tool_duration_ms)}</p>
                    <p className="text-xs text-ash">per tool call</p>
                  </div>
                </div>
              </div>

              {/* Token distribution charts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
                <DonutCard
                  title="Token Distribution by Model"
                  data={byModelData}
                  colors={CHART_COLORS}
                  totalLabel="total"
                  totalValue={fmtTokens(byModelData.reduce((s, d) => s + d.value, 0))}
                  legendFormatter={(item) => fmtTokens(item.value)}
                />
                <DonutCard
                  title="Prompt vs Completion"
                  data={pvcData}
                  colors={['#e11d48', '#8b5cf6']}
                  totalLabel="total"
                  totalValue={fmtTokens(pvcData.reduce((s, d) => s + d.value, 0))}
                  legendFormatter={(item) => fmtTokens(item.value)}
                />
              </div>

              <div className="flex justify-end">
                <Link
                  href={`/agents/${agentSlug}/lens/sessions`}
                  className="inline-flex items-center gap-2 px-4 py-2 border border-primary-600 text-primary-600 hover:bg-primary-50 rounded-lg text-sm font-medium transition-colors"
                >
                  View All Sessions
                  <ArrowLeft size={14} className="rotate-180" />
                </Link>
              </div>
            </>
          ) : null}
        </>
      )}

      {/* ── TOOLS TAB ─────────────────────────────────────────────────────── */}
      {tab === 'tools' && (
        <>
          {toolsLoading ? (
            <div className="text-ash py-16 text-center">Loading tool data…</div>
          ) : toolAnalytics ? (
            <>
              {/* Tool summary KPIs */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                <KpiCard
                  label="Total Calls"
                  value={toolAnalytics.total_calls.toLocaleString()}
                  icon={Wrench}
                  iconBg="bg-primary-50"
                  iconColor="text-primary-600"
                />
                <KpiCard
                  label="Success Rate"
                  value={fmtPct(toolAnalytics.overall_success_rate)}
                  icon={CheckCircle}
                  iconBg={toolAnalytics.overall_success_rate >= 0.95 ? 'bg-leaf-wash' : 'bg-sand-deep'}
                  iconColor={toolAnalytics.overall_success_rate >= 0.95 ? 'text-leaf' : 'text-warn'}
                />
                <KpiCard
                  label="Total Failures"
                  value={toolAnalytics.total_failures.toLocaleString()}
                  icon={XCircle}
                  iconBg={toolAnalytics.total_failures > 0 ? 'bg-blush-wash' : 'bg-cream'}
                  iconColor={toolAnalytics.total_failures > 0 ? 'text-danger' : 'text-ink-mute'}
                />
                <KpiCard
                  label="Unique Tools"
                  value={toolAnalytics.tools.length.toString()}
                  icon={Zap}
                  iconBg="bg-blush-wash"
                  iconColor="text-plum"
                />
              </div>

              {toolAnalytics.tools.length === 0 ? (
                <div className="rounded-xl border border-line bg-white p-12 text-center text-ash text-sm shadow-sm">
                  No tool calls recorded in this period. Tool calls will appear after an agent with tools is used.
                </div>
              ) : (
                <>
                  {/* Bar chart: calls by tool */}
                  <div className="rounded-xl border border-line bg-white p-5 mb-4 shadow-sm">
                    <h3 className="text-sm font-semibold text-ink-soft mb-4">Calls by Tool</h3>
                    <ResponsiveContainer width="100%" height={Math.max(180, toolBarData.length * 32)}>
                      <BarChart
                        data={toolBarData}
                        layout="vertical"
                        margin={{ top: 0, right: 16, bottom: 0, left: 140 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" horizontal={false} />
                        <XAxis type="number" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                        <YAxis
                          type="category"
                          dataKey="name"
                          tick={{ fontSize: 11, fill: '#374151' }}
                          axisLine={false}
                          tickLine={false}
                          width={136}
                        />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12 }}
                          formatter={(v: number, name: string) => [v, name === 'calls' ? 'Total calls' : 'Failures']}
                        />
                        <Bar dataKey="calls" fill="#e11d48" radius={[0, 4, 4, 0]} maxBarSize={20} />
                        <Bar dataKey="failures" fill="#f87171" radius={[0, 4, 4, 0]} maxBarSize={20} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Per-tool table */}
                  <div className="overflow-x-auto rounded-xl border border-line bg-white shadow-sm">
                    <table className="min-w-full divide-y divide-sand text-sm">
                      <thead className="bg-cream">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-ink-mute">Tool</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">Calls</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">Success</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">Failures</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">Avg Duration</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">Max Duration</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-ink-mute">Retries</th>
                          <th className="px-4 py-3 text-center text-xs font-medium text-ink-mute">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-sand">
                        {toolAnalytics.tools.map(tool => {
                          const pct = Math.round(tool.success_rate * 100)
                          const statusColor = pct >= 95 ? 'bg-leaf-wash text-forest' : pct >= 80 ? 'bg-sand-deep text-gold' : 'bg-blush-wash text-leaf'
                          return (
                            <tr key={tool.tool_name} className="hover:bg-cream">
                              <td className="px-4 py-3 font-mono text-xs text-ink max-w-[200px] truncate">{tool.tool_name}</td>
                              <td className="px-4 py-3 text-right text-ink-soft font-medium">{tool.total_calls}</td>
                              <td className="px-4 py-3 text-right text-forest">{tool.success_count}</td>
                              <td className="px-4 py-3 text-right text-danger font-medium">{tool.failure_count}</td>
                              <td className="px-4 py-3 text-right text-ink-soft">{fmtLatency(tool.avg_duration_ms)}</td>
                              <td className="px-4 py-3 text-right text-ink-mute">{fmtLatency(tool.max_duration_ms)}</td>
                              <td className="px-4 py-3 text-right text-ink-mute">{tool.total_retries}</td>
                              <td className="px-4 py-3 text-center">
                                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusColor}`}>
                                  {pct}%
                                </span>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="text-ash py-16 text-center">No tool data available</div>
          )}
        </>
      )}

      {/* ── TOOL ROI TAB ──────────────────────────────────────────────────── */}
      {tab === 'roi' && (
        <>
          {roiLoading ? (
            <div className="text-ash py-16 text-center">Analyzing tool ROI…</div>
          ) : toolROI ? (
            <ToolROIView data={toolROI} />
          ) : (
            <div className="text-ash py-16 text-center">No data available</div>
          )}
        </>
      )}

      {/* ── COMPACTION TAB ────────────────────────────────────────────────── */}
      {tab === 'compaction' && (
        <>
          {compactionLoading ? (
            <div className="text-ash py-16 text-center">Loading compaction data…</div>
          ) : compaction ? (
            <CompactionView data={compaction} />
          ) : (
            <div className="text-ash py-16 text-center">No compaction data available</div>
          )}
        </>
      )}

      {/* ── CACHE TAB ─────────────────────────────────────────────────────── */}
      {tab === 'cache' && (
        <>
          {cacheLoading ? (
            <div className="text-ash py-16 text-center">Loading cache data…</div>
          ) : cache ? (
            <CacheView data={cache} />
          ) : (
            <div className="text-ash py-16 text-center">No cache data available</div>
          )}
        </>
      )}

      {/* ── ALERTS TAB ────────────────────────────────────────────────────── */}
      {tab === 'alerts' && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-ink">Alert Rules</h2>
              <p className="text-sm text-ink-mute mt-0.5">Configure threshold-based alerts. Monitoring evaluation is coming soon.</p>
            </div>
            <button
              onClick={() => setShowAlertForm(!showAlertForm)}
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <Plus size={14} />New Alert
            </button>
          </div>

          {showAlertForm && (
            <div className="rounded-lg border border-line bg-white p-5 mb-4">
              <h3 className="text-sm font-semibold text-ink mb-4">New Alert</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {[
                  { label: 'Alert Name', field: 'name', type: 'text', placeholder: 'e.g. High failure rate' },
                ].map(({ label, field, type, placeholder }) => (
                  <div key={field}>
                    <label className="text-xs font-medium text-ink-soft mb-1 block">{label}</label>
                    <input
                      type={type}
                      value={(alertForm as any)[field]}
                      onChange={e => setAlertForm(f => ({ ...f, [field]: e.target.value }))}
                      className="w-full border border-taupe rounded-lg px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      placeholder={placeholder}
                    />
                  </div>
                ))}
                <div>
                  <label className="text-xs font-medium text-ink-soft mb-1 block">Metric</label>
                  <select value={alertForm.metric} onChange={e => setAlertForm(f => ({ ...f, metric: e.target.value as AlertCreateBody['metric'] }))} className="w-full border border-taupe rounded-lg px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent">
                    <option value="failure_rate">Failure Rate</option>
                    <option value="cost_per_session">Cost / Session</option>
                    <option value="avg_latency_ms">Avg Latency (ms)</option>
                    <option value="total_cost_usd">Total Cost (USD)</option>
                    <option value="token_count">Token Count</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-ink-soft mb-1 block">Condition</label>
                  <select value={alertForm.condition} onChange={e => setAlertForm(f => ({ ...f, condition: e.target.value as 'gt' | 'lt' }))} className="w-full border border-taupe rounded-lg px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent">
                    <option value="gt">Greater than (&gt;)</option>
                    <option value="lt">Less than (&lt;)</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-ink-soft mb-1 block">Threshold</label>
                  <input type="number" step="any" value={alertForm.threshold} onChange={e => setAlertForm(f => ({ ...f, threshold: parseFloat(e.target.value) || 0 }))} className="w-full border border-taupe rounded-lg px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent" />
                </div>
                <div>
                  <label className="text-xs font-medium text-ink-soft mb-1 block">Window (minutes)</label>
                  <input type="number" value={alertForm.window_minutes} onChange={e => setAlertForm(f => ({ ...f, window_minutes: parseInt(e.target.value) || 60 }))} className="w-full border border-taupe rounded-lg px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent" />
                </div>
                <div>
                  <label className="text-xs font-medium text-ink-soft mb-1 block">Notify via</label>
                  <select value={alertForm.notify_method} onChange={e => setAlertForm(f => ({ ...f, notify_method: e.target.value as 'email' | 'webhook' }))} className="w-full border border-taupe rounded-lg px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent">
                    <option value="email">Email</option>
                    <option value="webhook">Webhook</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-2 mt-4">
                <button onClick={handleCreateAlert} disabled={alertSaving || !alertForm.name} className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">
                  {alertSaving ? 'Saving…' : 'Create Alert'}
                </button>
                <button onClick={() => setShowAlertForm(false)} className="px-4 py-2 border border-taupe hover:bg-cream text-ink-soft rounded-lg text-sm transition-colors">
                  Cancel
                </button>
              </div>
            </div>
          )}

          {alerts.length === 0 ? (
            <div className="rounded-lg border border-line bg-white p-8 text-center text-ash text-sm">
              No alerts configured yet. Create one above.
            </div>
          ) : (
            <div className="space-y-2">
              {alerts.map(alert => (
                <div key={alert.id} className="rounded-lg border border-line bg-white p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {alert.is_active
                      ? <CheckCircle size={16} className="text-leaf shrink-0" />
                      : <XCircle size={16} className="text-ash shrink-0" />
                    }
                    <div>
                      <p className="text-sm font-medium text-ink">{alert.name}</p>
                      <p className="text-xs text-ink-mute">
                        {alert.metric} {alert.condition === 'gt' ? '>' : '<'} {alert.threshold} over {alert.window_minutes}m, {alert.notify_method}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1 text-xs text-warn bg-sand-deep border border-honey px-2 py-0.5 rounded">
                      <AlertTriangle size={11} />Monitoring coming soon
                    </span>
                    <button onClick={() => handleDeleteAlert(alert.id)} className="text-ash hover:text-leaf transition-colors">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      {/* ── QUALITY TAB ───────────────────────────────────────────────────── */}
      {tab === 'quality' && (
        <>
          {qualityLoading ? (
            <div className="text-ash py-16 text-center">Loading quality data…</div>
          ) : quality ? (
            <div className="space-y-6">
              {/* Satisfaction KPIs */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <KpiCard
                  label="Satisfaction Rate"
                  value={fmtPct(quality.satisfaction.satisfaction_rate)}
                  sub={`${quality.satisfaction.total_rated} rated messages`}
                  icon={Star}
                  iconBg={quality.satisfaction.satisfaction_rate >= 0.8 ? 'bg-leaf-wash' : quality.satisfaction.satisfaction_rate >= 0.6 ? 'bg-sand-deep' : 'bg-blush-wash'}
                  iconColor={quality.satisfaction.satisfaction_rate >= 0.8 ? 'text-leaf' : quality.satisfaction.satisfaction_rate >= 0.6 ? 'text-warn' : 'text-danger'}
                />
                <KpiCard
                  label="Thumbs Up"
                  value={String(quality.satisfaction.thumbs_up)}
                  icon={ThumbsUp}
                  iconBg="bg-leaf-wash"
                  iconColor="text-leaf"
                />
                <KpiCard
                  label="Thumbs Down"
                  value={String(quality.satisfaction.thumbs_down)}
                  icon={ThumbsDown}
                  iconBg="bg-blush-wash"
                  iconColor="text-leaf"
                />
                <KpiCard
                  label="Session Success"
                  value={fmtPct(quality.outcomes.success_rate)}
                  sub={`${quality.outcomes.success} of ${quality.outcomes.total_sessions}`}
                  icon={CheckCircle}
                  iconBg={quality.outcomes.success_rate >= 0.7 ? 'bg-leaf-wash' : 'bg-sand-deep'}
                  iconColor={quality.outcomes.success_rate >= 0.7 ? 'text-leaf' : 'text-warn'}
                />
              </div>

              {/* Outcome breakdown + channel breakdown */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <DonutCard
                  title="Session Outcomes"
                  data={[
                    { name: 'Success', value: quality.outcomes.success },
                    { name: 'Partial', value: quality.outcomes.partial },
                    { name: 'Failure', value: quality.outcomes.failure },
                    { name: 'Unknown', value: quality.outcomes.unknown },
                  ].filter(d => d.value > 0)}
                  colors={['#10b981', '#f59e0b', '#ef4444', '#9ca3af']}
                  totalLabel="sessions"
                  totalValue={String(quality.outcomes.total_sessions)}
                  legendFormatter={(item) => String(item.value)}
                />
                {quality.outcomes.total_sessions > 0 && (
                  <div className="mt-3 rounded-lg border border-sand bg-cream px-4 py-2 grid grid-cols-2 gap-2 text-xs text-ink-mute">
                    <div>Explicit rate: <span className="font-medium text-ink-soft">{fmtPct(quality.outcomes.explicit_rate)}</span></div>
                    <div>Implicit rate: <span className="font-medium text-ink-soft">{fmtPct(quality.outcomes.implicit_rate)}</span></div>
                  </div>
                )}

                <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
                  <h3 className="text-sm font-semibold text-ink mb-4">Satisfaction by Channel</h3>
                  {quality.satisfaction.by_channel.length > 0 ? (
                    <div className="space-y-3">
                      {quality.satisfaction.by_channel.map(ch => {
                        const pct = Math.round(ch.satisfaction_rate * 100)
                        const barColor = pct >= 80 ? 'bg-leaf' : pct >= 60 ? 'bg-warn' : 'bg-ink'
                        return (
                          <div key={ch.channel}>
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-medium text-ink-soft capitalize">{ch.channel}</span>
                              <span className="text-xs text-ink-mute">{pct}%, {ch.rated_count} rated</span>
                            </div>
                            <div className="h-1.5 bg-sand rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-40 text-ash text-sm">No channel data yet</div>
                  )}
                </div>
              </div>

              {/* Top disliked tools */}
              {quality.top_disliked_tools.length > 0 && (
                <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
                  <h3 className="text-sm font-semibold text-ink mb-3">Most Disliked Tool Calls</h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-sand text-sm">
                      <thead className="bg-cream">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-ink-mute">Tool</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-ink-mute">Dislikes</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-ink-mute">Dislike Rate</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-sand">
                        {quality.top_disliked_tools.map(t => (
                          <tr key={t.tool_name} className="hover:bg-cream">
                            <td className="px-4 py-2 font-mono text-xs text-ink">{t.tool_name}</td>
                            <td className="px-4 py-2 text-right text-ink-soft">{t.dislike_count}</td>
                            <td className="px-4 py-2 text-right text-leaf font-medium">{fmtPct(t.dislike_rate)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="rounded-lg border border-sand bg-cream px-4 py-3 text-xs text-ink-mute leading-relaxed">
                <span className="font-medium text-ink-soft">Quality signals: </span>
                Satisfaction rate comes from thumbs up/down votes on individual messages.
                Session outcomes combine explicit feedback ("Did this help?") with implicit signals
                (conversation completion, tool success patterns).
              </div>
            </div>
          ) : (
            <div className="text-ash py-16 text-center">No quality data available</div>
          )}
        </>
      )}

      {/* ── EVAL TAB ──────────────────────────────────────────────────────── */}
      {tab === 'eval' && (
        <div className="space-y-6">
          {evalLoading ? (
            <div className="text-ash py-16 text-center">Loading eval data…</div>
          ) : (
            <>
              {/* Dataset management */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Left: dataset list + create */}
                <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-semibold text-ink">Datasets</h3>
                  </div>

                  {/* Create dataset */}
                  <div className="flex gap-2 mb-4">
                    <input
                      value={newDatasetName}
                      onChange={e => setNewDatasetName(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleCreateDataset()}
                      placeholder="New dataset name"
                      className="flex-1 border border-taupe rounded-lg px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                    <button
                      onClick={handleCreateDataset}
                      disabled={datasetCreating || !newDatasetName.trim()}
                      className="inline-flex items-center gap-1.5 px-3 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                    >
                      <Plus size={14} />{datasetCreating ? '...' : 'Create'}
                    </button>
                  </div>

                  {datasets.length === 0 ? (
                    <div className="text-ash text-sm text-center py-8">No datasets yet. Create one above.</div>
                  ) : (
                    <div className="space-y-1.5">
                      {datasets.map(ds => (
                        <div
                          key={ds.dataset_id}
                          onClick={() => handleSelectDataset(ds)}
                          className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors ${
                            selectedDataset?.dataset_id === ds.dataset_id
                              ? 'border-primary-500 bg-primary-50'
                              : 'border-line hover:bg-cream'
                          }`}
                        >
                          <div>
                            <p className="text-sm font-medium text-ink">{ds.name}</p>
                            <p className="text-xs text-ink-mute">{ds.case_count} case{ds.case_count !== 1 ? 's' : ''}</p>
                          </div>
                          <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                            <button
                              onClick={() => handleTriggerRun(ds.dataset_id)}
                              disabled={runTriggering === ds.dataset_id}
                              className="inline-flex items-center gap-1 px-2.5 py-1 bg-leaf hover:bg-forest disabled:opacity-50 text-white rounded text-xs font-medium transition-colors"
                              title="Run eval"
                            >
                              <Play size={11} />{runTriggering === ds.dataset_id ? '...' : 'Run'}
                            </button>
                            <button
                              onClick={() => handleDeleteDataset(ds.dataset_id)}
                              className="text-ash hover:text-leaf transition-colors p-1"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Right: cases for selected dataset */}
                <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
                  <h3 className="text-sm font-semibold text-ink mb-4">
                    {selectedDataset ? `Cases, ${selectedDataset.name}` : 'Cases'}
                  </h3>

                  {!selectedDataset ? (
                    <div className="text-ash text-sm text-center py-8">Select a dataset to manage cases</div>
                  ) : (
                    <>
                      {/* Add case */}
                      <div className="space-y-2 mb-4">
                        <textarea
                          value={newCaseInput}
                          onChange={e => setNewCaseInput(e.target.value)}
                          placeholder="User input (e.g. 'What is the capital of France?')"
                          rows={2}
                          className="w-full border border-taupe rounded-lg px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
                        />
                        <textarea
                          value={newCaseCriteria}
                          onChange={e => setNewCaseCriteria(e.target.value)}
                          placeholder="Expected criteria (e.g. 'Response should mention Paris')"
                          rows={2}
                          className="w-full border border-taupe rounded-lg px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
                        />
                        <button
                          onClick={handleAddCase}
                          disabled={caseAdding || !newCaseInput.trim() || !newCaseCriteria.trim()}
                          className="inline-flex items-center gap-1.5 px-3 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
                        >
                          <Plus size={14} />{caseAdding ? 'Adding…' : 'Add Case'}
                        </button>
                      </div>

                      {cases.length === 0 ? (
                        <div className="text-ash text-sm text-center py-6">No cases yet. Add one above.</div>
                      ) : (
                        <div className="space-y-2 max-h-72 overflow-y-auto">
                          {cases.map(c => (
                            <div key={c.case_id} className="flex items-start gap-2 p-3 rounded-lg border border-sand bg-cream">
                              <div className="flex-1 min-w-0">
                                <p className="text-xs font-medium text-ink truncate">{c.input}</p>
                                <p className="text-xs text-ink-mute mt-0.5 truncate">{c.expected_criteria}</p>
                              </div>
                              <button
                                onClick={() => handleDeleteCase(c.case_id)}
                                className="text-ash hover:text-leaf transition-colors shrink-0 mt-0.5"
                              >
                                <Trash2 size={12} />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Run history */}
              <div className="rounded-xl border border-line bg-white shadow-sm">
                <div className="px-5 py-4 border-b border-sand">
                  <h3 className="text-sm font-semibold text-ink">Run History</h3>
                </div>
                {!evalHistory || evalHistory.runs.length === 0 ? (
                  <div className="p-8 text-center text-ash text-sm">
                    No eval runs yet. Select a dataset and click Run to start one.
                  </div>
                ) : (
                  <div className="divide-y divide-sand">
                    {evalHistory.runs.map(run => {
                      const isExpanded = expandedRun === run.run_id
                      const statusColor = run.status === 'completed'
                        ? 'bg-leaf-wash text-forest'
                        : run.status === 'running'
                        ? 'bg-sky-wash text-azure'
                        : run.status === 'failed'
                        ? 'bg-blush-wash text-danger'
                        : 'bg-sand text-ink-soft'
                      const passColor = run.pass_rate >= 0.8 ? 'text-leaf' : run.pass_rate >= 0.6 ? 'text-warn' : 'text-danger'
                      return (
                        <div key={run.run_id}>
                          <div
                            className="flex items-center gap-3 px-5 py-3 cursor-pointer hover:bg-cream"
                            onClick={() => handleExpandRun(run.run_id)}
                          >
                            {isExpanded ? <ChevronDown size={14} className="text-ash shrink-0" /> : <ChevronRight size={14} className="text-ash shrink-0" />}
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-ink truncate">{run.dataset_name || run.dataset_id.slice(0, 8)}</p>
                              <p className="text-xs text-ash">{run.ran_at ? new Date(run.ran_at).toLocaleString() : '—'}</p>
                            </div>
                            <span className={`text-xs font-medium px-2 py-0.5 rounded ${statusColor}`}>{run.status}</span>
                            <span className={`text-sm font-bold ${passColor} w-16 text-right`}>{fmtPct(run.pass_rate)}</span>
                            <span className="text-xs text-ash w-20 text-right">{run.passed}/{run.total_cases} passed</span>
                            <span className="text-xs text-ash w-16 text-right">{(run.avg_score * 100).toFixed(0)}% score</span>
                          </div>
                          {isExpanded && (
                            <div className="px-5 pb-4 bg-cream border-t border-sand">
                              {runResults[run.run_id] ? (
                                runResults[run.run_id].length === 0 ? (
                                  <p className="text-xs text-ash py-3">No results yet</p>
                                ) : (
                                  <div className="space-y-2 mt-3">
                                    {runResults[run.run_id].map(r => (
                                      <div key={r.result_id} className={`rounded-lg border p-3 ${r.passed ? 'border-mint bg-leaf-wash' : 'border-blush bg-blush-wash'}`}>
                                        <div className="flex items-start gap-2">
                                          {r.passed
                                            ? <CheckCircle size={13} className="text-leaf shrink-0 mt-0.5" />
                                            : <XCircle size={13} className="text-leaf shrink-0 mt-0.5" />
                                          }
                                          <div className="flex-1 min-w-0">
                                            <p className="text-xs font-medium text-ink mb-0.5 truncate">{r.input}</p>
                                            <p className="text-xs text-ink-mute mb-1 line-clamp-2">{r.reasoning}</p>
                                            <div className="flex items-center gap-3 text-xs text-ash">
                                              <span>Score: <span className="font-medium text-ink-soft">{(r.score * 100).toFixed(0)}%</span></span>
                                              <span>Latency: <span className="font-medium text-ink-soft">{fmtLatency(r.latency_ms)}</span></span>
                                            </div>
                                          </div>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )
                              ) : (
                                <p className="text-xs text-ash py-3">Loading results…</p>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      </div>
    </AgentPageShell>
  )
}
