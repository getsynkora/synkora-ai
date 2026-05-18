'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft, Activity, Bell, Plus, Trash2, CheckCircle, XCircle,
  AlertTriangle, Wrench, Zap, DollarSign, Clock, TrendingUp, BarChart2,
  ThumbsUp, ThumbsDown, Minus, Scissors, Database,
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
  createLensAlert,
  deleteLensAlert,
  type LensOverviewResponse,
  type LensTokenDistributionResponse,
  type LensToolAnalyticsResponse,
  type LensToolROIResponse,
  type LensToolROIStat,
  type LensCompactionAnalyticsResponse,
  type LensCacheAnalyticsResponse,
  type AlertResponse,
  type AlertCreateBody,
  type LensRange,
} from '@/lib/api/agent-lens'
import AgentPageShell, { AgentPagePanel, AgentPageTabs } from '@/components/agents/AgentPageShell'

type Tab = 'overview' | 'tools' | 'roi' | 'compaction' | 'cache' | 'alerts'

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
    <div className="rounded-xl border border-gray-200 bg-white p-5 flex items-start gap-3 shadow-sm">
      <div className={`rounded-full p-2.5 shrink-0 ${iconBg}`}>
        <Icon className={`h-4 w-4 ${iconColor}`} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-gray-500 mb-0.5">{label}</p>
        <p className="text-3xl font-bold text-gray-900 leading-none">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
      </div>
    </div>
  )
}

function SuccessRateBar({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100)
  const color = pct >= 95 ? 'bg-primary-500' : pct >= 80 ? 'bg-amber-500' : 'bg-red-500'
  const textColor = pct >= 95 ? 'text-primary-600' : pct >= 80 ? 'text-amber-700' : 'text-red-700'
  const bg = pct >= 95 ? 'bg-primary-50 border-primary-200' : pct >= 80 ? 'bg-amber-50 border-amber-200' : 'bg-red-50 border-red-200'
  return (
    <div className={`rounded-xl border p-5 shadow-sm ${bg}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-gray-500">Tool Success Rate</span>
        <span className={`text-3xl font-bold ${textColor}`}>{pct}%</span>
      </div>
      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
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
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">{title}</h3>
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
              <span className="text-base font-bold text-gray-900">{totalValue}</span>
              <span className="text-xs text-gray-400">{totalLabel}</span>
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
                  <span className="text-gray-600 truncate">{item.name}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0 ml-2">
                  <span className="text-gray-800 font-medium">{legendFormatter(item)}</span>
                  <span className="text-gray-400 w-10 text-right">
                    {total > 0 ? `${Math.round((item.value / total) * 100)}%` : '0%'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="flex items-center justify-center h-40 text-gray-400 text-sm">No data yet</div>
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
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
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
          iconBg={pruningPct > 30 ? 'bg-amber-50' : 'bg-primary-50'}
          iconColor={pruningPct > 30 ? 'text-amber-600' : 'text-primary-600'}
        />
        <KpiCard
          label="Tokens Saved"
          value={fmtTokens(data.total_tokens_saved)}
          sub={`avg ${fmtTokens(Math.round(data.avg_tokens_saved_per_session))} / session`}
          icon={TrendingUp}
          iconBg="bg-emerald-50"
          iconColor="text-emerald-600"
        />
        <KpiCard
          label="Data Tools Trimmed"
          value={String(data.data_bearing_pruned_total)}
          sub="SQL/file results affected"
          icon={AlertTriangle}
          iconBg={hasDataWarning ? 'bg-amber-50' : 'bg-gray-50'}
          iconColor={hasDataWarning ? 'text-amber-600' : 'text-gray-400'}
        />
        <KpiCard
          label="Avg Pruning Ratio"
          value={`${ratiosPct}%`}
          sub={`${data.total_results_pruned} of ${data.total_results_evaluated} results`}
          icon={BarChart2}
          iconBg="bg-violet-50"
          iconColor="text-violet-600"
        />
      </div>

      {/* Trend chart */}
      {trendData.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Pruning Events Over Time</h3>
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
          <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
            <span className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-5 bg-[#e11d48]" />Pruning events</span>
            <span className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-5 bg-[#f59e0b]" />Data tools trimmed</span>
          </div>
        </div>
      )}

      {/* Explanation */}
      <div className="rounded-lg border border-gray-100 bg-gray-50 px-4 py-3 text-xs text-gray-500 leading-relaxed">
        <span className="font-medium text-gray-700">How compaction works: </span>
        When a conversation grows too long, older tool results are compacted to free context space.
        Non-data tools (e.g. send_email) get a 1-line summary. Data-bearing tools (SQL queries, CSV reads) are
        trimmed with head+tail preservation to keep data rows intact — but heavy trimming can still degrade quality.
        The <span className="font-medium text-amber-700">Data Tools Trimmed</span> counter shows how often this
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

  const ctxColor = avgCtxPct >= 80 ? 'text-red-700' : avgCtxPct >= 60 ? 'text-amber-700' : 'text-emerald-700'
  const ctxBg = avgCtxPct >= 80 ? 'bg-red-50 border-red-200' : avgCtxPct >= 60 ? 'bg-amber-50 border-amber-200' : 'bg-emerald-50 border-emerald-200'

  return (
    <div className="space-y-6">
      {/* Context pressure warning */}
      {data.high_pressure_calls > 0 && (
        <div className={`rounded-lg border px-4 py-3 text-sm ${avgCtxPct >= 80 ? 'border-red-300 bg-red-50 text-red-800' : 'border-amber-300 bg-amber-50 text-amber-800'}`}>
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
          iconBg={hitPct >= 50 ? 'bg-emerald-50' : 'bg-gray-50'}
          iconColor={hitPct >= 50 ? 'text-emerald-600' : 'text-gray-400'}
        />
        <KpiCard
          label="Est. Savings"
          value={fmtCost(data.estimated_savings_usd)}
          sub="from cache reads"
          icon={DollarSign}
          iconBg="bg-emerald-50"
          iconColor="text-emerald-600"
        />
        <KpiCard
          label="Avg Context Use"
          value={`${avgCtxPct}%`}
          sub={`max ${maxCtxPct}%`}
          icon={TrendingUp}
          iconBg={avgCtxPct >= 80 ? 'bg-red-50' : avgCtxPct >= 60 ? 'bg-amber-50' : 'bg-emerald-50'}
          iconColor={avgCtxPct >= 80 ? 'text-red-600' : avgCtxPct >= 60 ? 'text-amber-600' : 'text-emerald-600'}
        />
        <KpiCard
          label="High Pressure Calls"
          value={String(data.high_pressure_calls)}
          sub="≥80% context used"
          icon={AlertTriangle}
          iconBg={data.high_pressure_calls > 0 ? 'bg-amber-50' : 'bg-gray-50'}
          iconColor={data.high_pressure_calls > 0 ? 'text-amber-600' : 'text-gray-400'}
        />
      </div>

      {/* Context utilization gauge */}
      <div className={`rounded-xl border p-5 shadow-sm ${ctxBg}`}>
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-medium text-gray-600">Average Context Window Utilization</span>
          <span className={`text-3xl font-bold ${ctxColor}`}>{avgCtxPct}%</span>
        </div>
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${avgCtxPct >= 80 ? 'bg-red-500' : avgCtxPct >= 60 ? 'bg-amber-500' : 'bg-emerald-500'}`}
            style={{ width: `${Math.min(avgCtxPct, 100)}%` }}
          />
        </div>
        <div className="mt-2 flex justify-between text-xs text-gray-400">
          <span>0%</span>
          <span className="text-amber-600 font-medium">60% caution</span>
          <span className="text-red-600 font-medium">80% critical</span>
          <span>100%</span>
        </div>
      </div>

      {/* Token stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Total Input Tokens', value: fmtTokens(data.total_input_tokens), color: 'border-l-gray-400' },
          { label: 'Cache Read Tokens', value: fmtTokens(data.total_cache_read_tokens), color: 'border-l-emerald-500' },
          { label: 'Cache Creation Tokens', value: fmtTokens(data.total_cache_creation_tokens), color: 'border-l-violet-500' },
        ].map(item => (
          <div key={item.label} className={`rounded-xl border border-gray-200 bg-white p-4 shadow-sm border-l-4 ${item.color}`}>
            <p className="text-xs font-medium text-gray-500 mb-1">{item.label}</p>
            <p className="text-2xl font-bold text-gray-900">{item.value}</p>
          </div>
        ))}
      </div>

      {/* Trend chart */}
      {trendData.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Cache Hit Rate Over Time</h3>
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
      <div className="rounded-lg border border-gray-100 bg-gray-50 px-4 py-3 text-xs text-gray-500 leading-relaxed">
        <span className="font-medium text-gray-700">Prompt cache: </span>
        Anthropic's prompt caching stores common prefix tokens (system prompt, tools) server-side.
        Cache reads cost ~10% of normal input token price, saving cost on repeated calls.
        A high hit rate means the agent is reusing context efficiently.
        Context utilization tracks how much of the model's context window is used per call — sustained
        usage above 80% leads to compaction and potential quality degradation.
      </div>
    </div>
  )
}

// ─── Tool ROI ─────────────────────────────────────────────────────────────────

const VERDICT_CONFIG = {
  keep:    { label: 'Keep',              bg: 'bg-green-100',  text: 'text-green-700',  border: 'border-green-200',  Icon: ThumbsUp },
  review:  { label: 'Review',            bg: 'bg-amber-100',  text: 'text-amber-700',  border: 'border-amber-200',  Icon: AlertTriangle },
  remove:  { label: 'May be unnecessary', bg: 'bg-red-100',  text: 'text-red-700',    border: 'border-red-200',    Icon: ThumbsDown },
  neutral: { label: 'Insufficient data', bg: 'bg-gray-100',  text: 'text-gray-500',   border: 'border-gray-200',   Icon: Minus },
} as const

function LiftBadge({ lift }: { lift: number }) {
  const pct = (lift * 100).toFixed(1)
  if (Math.abs(lift) < 0.01) return <span className="text-gray-400 text-xs">—</span>
  return lift > 0
    ? <span className="text-green-700 font-semibold text-sm">+{pct}%</span>
    : <span className="text-red-600 font-semibold text-sm">{pct}%</span>
}

function CostImpactBadge({ pct }: { pct: number }) {
  const label = `${pct >= 0 ? '+' : ''}${(pct * 100).toFixed(1)}%`
  if (Math.abs(pct) < 0.005) return <span className="text-gray-400 text-xs">—</span>
  return <span className={`text-xs font-medium ${pct > 0.1 ? 'text-orange-600' : pct < -0.05 ? 'text-green-600' : 'text-gray-600'}`}>{label}</span>
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
    ? `Consider removing ${topRemoval.tool_name} — sessions using it resolve ${Math.abs(topRemoval.completion_lift * 100).toFixed(0)}% less often than sessions without it.`
    : worstReview
    ? `${worstReview.tool_name} is called ${worstReview.calls_per_session.toFixed(1)}×/session but shows only ${(worstReview.completion_lift * 100).toFixed(1)}% completion lift — worth reviewing.`
    : keeps > 0
    ? `All ${keeps} tracked tool${keeps > 1 ? 's are' : ' is'} contributing positively to session resolution.`
    : null

  return (
    <div>
      {/* Summary bar */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-50 border border-gray-200 text-sm text-gray-600">
          <BarChart2 size={14} className="text-gray-400" />
          <span className="font-medium">{tools.length}</span> tools · <span className="font-medium">{data.total_sessions}</span> sessions analyzed
        </div>
        {keeps > 0 && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-50 border border-green-200 text-sm text-green-700">
            <ThumbsUp size={13} /><span className="font-medium">{keeps}</span> helping
          </div>
        )}
        {reviews > 0 && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-700">
            <AlertTriangle size={13} /><span className="font-medium">{reviews}</span> need review
          </div>
        )}
        {removes > 0 && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
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
        <div className="rounded-xl border border-gray-200 bg-white p-12 text-center text-gray-400 text-sm shadow-sm">
          No tool call data in this period. ROI analysis requires tool calls to be recorded.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-100 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tool</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Calls / Session</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Error %</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Completion Lift
                  <span className="block text-gray-400 font-normal normal-case text-[10px]">sessions with vs without</span>
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Cost Impact
                  <span className="block text-gray-400 font-normal normal-case text-[10px]">vs sessions without</span>
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Sessions With</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Verdict</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {tools.map(tool => {
                const vc = VERDICT_CONFIG[tool.verdict as keyof typeof VERDICT_CONFIG] ?? VERDICT_CONFIG.neutral
                const VIcon = vc.Icon
                const errorPct = Math.round(tool.error_rate * 100)
                const errorColor = errorPct > 15 ? 'text-red-600 font-semibold' : errorPct > 5 ? 'text-amber-600' : 'text-gray-500'
                return (
                  <tr key={tool.tool_name} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-gray-900">{tool.tool_name}</span>
                      <div className="text-[10px] text-gray-400 mt-0.5">{tool.total_calls.toLocaleString()} total calls</div>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700 font-medium">{tool.calls_per_session.toFixed(1)}</td>
                    <td className={`px-4 py-3 text-right ${errorColor}`}>{errorPct}%</td>
                    <td className="px-4 py-3 text-right">
                      <LiftBadge lift={tool.completion_lift} />
                      <div className="text-[10px] text-gray-400 mt-0.5">
                        {Math.round(tool.completion_rate_with * 100)}% with · {Math.round(tool.completion_rate_without * 100)}% without
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <CostImpactBadge pct={tool.cost_impact_pct} />
                      <div className="text-[10px] text-gray-400 mt-0.5">
                        ${tool.avg_cost_with.toFixed(4)} vs ${tool.avg_cost_without.toFixed(4)}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600">
                      {tool.sessions_with.toLocaleString()}
                      <div className="text-[10px] text-gray-400">{tool.sessions_without} without</div>
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
      <div className="mt-4 rounded-lg border border-gray-100 bg-gray-50 px-4 py-3 text-xs text-gray-500 leading-relaxed">
        <span className="font-medium text-gray-700">How verdicts are assigned: </span>
        <span className="font-medium text-green-700">Keep</span> = tool clearly improves session resolution rate (&gt;5% lift).
        {' '}<span className="font-medium text-amber-700">Review</span> = negative lift or high error rate — may be hurting more than helping.
        {' '}<span className="font-medium text-red-700">May be unnecessary</span> = sessions with this tool resolve significantly less often (&gt;15% worse) or fail &gt;50% of the time.
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

  const [loading, setLoading] = useState(true)
  const [toolsLoading, setToolsLoading] = useState(false)
  const [roiLoading, setRoiLoading] = useState(false)
  const [compactionLoading, setCompactionLoading] = useState(false)
  const [cacheLoading, setCacheLoading] = useState(false)
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

  useEffect(() => { loadOverview() }, [loadOverview])
  useEffect(() => { if (tab === 'tools') loadToolAnalytics() }, [tab, loadToolAnalytics])
  useEffect(() => { if (tab === 'roi') loadROI() }, [tab, loadROI])
  useEffect(() => { if (tab === 'compaction') loadCompaction() }, [tab, loadCompaction])
  useEffect(() => { if (tab === 'cache') loadCache() }, [tab, loadCache])
  useEffect(() => { if (tab === 'alerts') loadAlerts() }, [tab, loadAlerts])

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
      backHref={`/agents/${agentSlug}/view`}
      backLabel="Back to Agent"
      badge="Analytics"
      maxWidthClassName="max-w-[88rem]"
      actions={
        <div className="rounded-[1.1rem] border border-black/10 bg-white/80 p-1.5 shadow-[0_12px_28px_rgba(0,0,0,0.04)]">
          <div className="flex flex-wrap gap-1.5">
            {RANGE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setRange(opt.value)}
                className={`rounded-[0.9rem] px-3.5 py-2 text-sm font-semibold transition-colors ${
                  range === opt.value
                    ? 'bg-[#171717] text-white'
                    : 'text-gray-600 hover:bg-[#f7f2e7] hover:text-[#171717]'
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
          ]}
        />

        {error ? (
          <AgentPagePanel className="border-[#eed6dd] bg-[linear-gradient(180deg,_rgba(252,245,247,0.98),_rgba(249,236,240,0.96))] p-4">
            <p className="text-sm text-[#8a445c]">{error}</p>
          </AgentPagePanel>
        ) : null}

      {/* ── OVERVIEW TAB ───────────────────────────────────────────────────── */}
      {tab === 'overview' && (
        <>
          {loading ? (
            <div className="text-gray-400 py-16 text-center">Loading...</div>
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
                  iconBg="bg-violet-50"
                  iconColor="text-violet-600"
                />
                <KpiCard
                  label="Total Tokens"
                  value={fmtTokens(stats.total_tokens)}
                  sub={`${fmtTokens(stats.input_tokens)} in · ${fmtTokens(stats.output_tokens)} out`}
                  icon={TrendingUp}
                  iconBg="bg-violet-50"
                  iconColor="text-violet-500"
                />
                <KpiCard
                  label="Total Cost"
                  value={fmtCost(stats.total_cost_usd)}
                  sub={`${fmtCost(stats.avg_cost_per_session)} / session`}
                  icon={DollarSign}
                  iconBg="bg-emerald-50"
                  iconColor="text-emerald-600"
                />
                <KpiCard
                  label="Avg Latency"
                  value={fmtLatency(stats.avg_latency_ms)}
                  icon={Clock}
                  iconBg="bg-amber-50"
                  iconColor="text-amber-600"
                />
                <KpiCard
                  label="Tool Calls"
                  value={stats.total_tool_calls.toLocaleString()}
                  sub={`${stats.failed_tool_calls} failed`}
                  icon={Wrench}
                  iconBg={stats.failed_tool_calls > 0 ? 'bg-red-50' : 'bg-primary-50'}
                  iconColor={stats.failed_tool_calls > 0 ? 'text-red-600' : 'text-primary-600'}
                />
              </div>

              {/* Health + success rate */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
                <SuccessRateBar rate={stats.total_tool_calls > 0 ? 1 - stats.failure_rate : 1} />

                <div className="rounded-xl border border-gray-200 bg-white p-5 flex items-center gap-4 shadow-sm">
                  <div className="rounded-full bg-amber-50 p-3">
                    <AlertTriangle className="h-5 w-5 text-amber-600" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-gray-500 mb-0.5">Failed Calls</p>
                    <p className="text-3xl font-bold text-gray-900">{stats.failed_tool_calls}</p>
                    <p className="text-xs text-gray-400">of {stats.total_tool_calls} total</p>
                  </div>
                </div>

                <div className="rounded-xl border border-gray-200 bg-white p-5 flex items-center gap-4 shadow-sm">
                  <div className="rounded-full bg-teal-50 p-3">
                    <Clock className="h-5 w-5 text-teal-600" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-gray-500 mb-0.5">Avg Tool Duration</p>
                    <p className="text-3xl font-bold text-gray-900">{fmtLatency(stats.avg_tool_duration_ms)}</p>
                    <p className="text-xs text-gray-400">per tool call</p>
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
            <div className="text-gray-400 py-16 text-center">Loading tool data...</div>
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
                  iconBg={toolAnalytics.overall_success_rate >= 0.95 ? 'bg-green-50' : 'bg-amber-50'}
                  iconColor={toolAnalytics.overall_success_rate >= 0.95 ? 'text-green-600' : 'text-amber-600'}
                />
                <KpiCard
                  label="Total Failures"
                  value={toolAnalytics.total_failures.toLocaleString()}
                  icon={XCircle}
                  iconBg={toolAnalytics.total_failures > 0 ? 'bg-red-50' : 'bg-gray-50'}
                  iconColor={toolAnalytics.total_failures > 0 ? 'text-red-600' : 'text-gray-500'}
                />
                <KpiCard
                  label="Unique Tools"
                  value={toolAnalytics.tools.length.toString()}
                  icon={Zap}
                  iconBg="bg-violet-50"
                  iconColor="text-violet-600"
                />
              </div>

              {toolAnalytics.tools.length === 0 ? (
                <div className="rounded-xl border border-gray-200 bg-white p-12 text-center text-gray-400 text-sm shadow-sm">
                  No tool calls recorded in this period. Tool calls will appear after an agent with tools is used.
                </div>
              ) : (
                <>
                  {/* Bar chart: calls by tool */}
                  <div className="rounded-xl border border-gray-200 bg-white p-5 mb-4 shadow-sm">
                    <h3 className="text-sm font-semibold text-gray-700 mb-4">Calls by Tool</h3>
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
                  <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
                    <table className="min-w-full divide-y divide-gray-100 text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tool</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Calls</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Success</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Failures</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Avg Duration</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Max Duration</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Retries</th>
                          <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {toolAnalytics.tools.map(tool => {
                          const pct = Math.round(tool.success_rate * 100)
                          const statusColor = pct >= 95 ? 'bg-green-100 text-green-700' : pct >= 80 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'
                          return (
                            <tr key={tool.tool_name} className="hover:bg-gray-50">
                              <td className="px-4 py-3 font-mono text-xs text-gray-900 max-w-[200px] truncate">{tool.tool_name}</td>
                              <td className="px-4 py-3 text-right text-gray-700 font-medium">{tool.total_calls}</td>
                              <td className="px-4 py-3 text-right text-green-700">{tool.success_count}</td>
                              <td className="px-4 py-3 text-right text-red-600 font-medium">{tool.failure_count}</td>
                              <td className="px-4 py-3 text-right text-gray-600">{fmtLatency(tool.avg_duration_ms)}</td>
                              <td className="px-4 py-3 text-right text-gray-500">{fmtLatency(tool.max_duration_ms)}</td>
                              <td className="px-4 py-3 text-right text-gray-500">{tool.total_retries}</td>
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
            <div className="text-gray-400 py-16 text-center">No tool data available</div>
          )}
        </>
      )}

      {/* ── TOOL ROI TAB ──────────────────────────────────────────────────── */}
      {tab === 'roi' && (
        <>
          {roiLoading ? (
            <div className="text-gray-400 py-16 text-center">Analyzing tool ROI...</div>
          ) : toolROI ? (
            <ToolROIView data={toolROI} />
          ) : (
            <div className="text-gray-400 py-16 text-center">No data available</div>
          )}
        </>
      )}

      {/* ── COMPACTION TAB ────────────────────────────────────────────────── */}
      {tab === 'compaction' && (
        <>
          {compactionLoading ? (
            <div className="text-gray-400 py-16 text-center">Loading compaction data...</div>
          ) : compaction ? (
            <CompactionView data={compaction} />
          ) : (
            <div className="text-gray-400 py-16 text-center">No compaction data available</div>
          )}
        </>
      )}

      {/* ── CACHE TAB ─────────────────────────────────────────────────────── */}
      {tab === 'cache' && (
        <>
          {cacheLoading ? (
            <div className="text-gray-400 py-16 text-center">Loading cache data...</div>
          ) : cache ? (
            <CacheView data={cache} />
          ) : (
            <div className="text-gray-400 py-16 text-center">No cache data available</div>
          )}
        </>
      )}

      {/* ── ALERTS TAB ────────────────────────────────────────────────────── */}
      {tab === 'alerts' && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Alert Rules</h2>
              <p className="text-sm text-gray-500 mt-0.5">Configure threshold-based alerts. Monitoring evaluation is coming soon.</p>
            </div>
            <button
              onClick={() => setShowAlertForm(!showAlertForm)}
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              <Plus size={14} />New Alert
            </button>
          </div>

          {showAlertForm && (
            <div className="rounded-lg border border-gray-200 bg-white p-5 mb-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-4">New Alert</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {[
                  { label: 'Alert Name', field: 'name', type: 'text', placeholder: 'e.g. High failure rate' },
                ].map(({ label, field, type, placeholder }) => (
                  <div key={field}>
                    <label className="text-xs font-medium text-gray-600 mb-1 block">{label}</label>
                    <input
                      type={type}
                      value={(alertForm as any)[field]}
                      onChange={e => setAlertForm(f => ({ ...f, [field]: e.target.value }))}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      placeholder={placeholder}
                    />
                  </div>
                ))}
                <div>
                  <label className="text-xs font-medium text-gray-600 mb-1 block">Metric</label>
                  <select value={alertForm.metric} onChange={e => setAlertForm(f => ({ ...f, metric: e.target.value as AlertCreateBody['metric'] }))} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent">
                    <option value="failure_rate">Failure Rate</option>
                    <option value="cost_per_session">Cost / Session</option>
                    <option value="avg_latency_ms">Avg Latency (ms)</option>
                    <option value="total_cost_usd">Total Cost (USD)</option>
                    <option value="token_count">Token Count</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600 mb-1 block">Condition</label>
                  <select value={alertForm.condition} onChange={e => setAlertForm(f => ({ ...f, condition: e.target.value as 'gt' | 'lt' }))} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent">
                    <option value="gt">Greater than (&gt;)</option>
                    <option value="lt">Less than (&lt;)</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600 mb-1 block">Threshold</label>
                  <input type="number" step="any" value={alertForm.threshold} onChange={e => setAlertForm(f => ({ ...f, threshold: parseFloat(e.target.value) || 0 }))} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600 mb-1 block">Window (minutes)</label>
                  <input type="number" value={alertForm.window_minutes} onChange={e => setAlertForm(f => ({ ...f, window_minutes: parseInt(e.target.value) || 60 }))} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600 mb-1 block">Notify via</label>
                  <select value={alertForm.notify_method} onChange={e => setAlertForm(f => ({ ...f, notify_method: e.target.value as 'email' | 'webhook' }))} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent">
                    <option value="email">Email</option>
                    <option value="webhook">Webhook</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-2 mt-4">
                <button onClick={handleCreateAlert} disabled={alertSaving || !alertForm.name} className="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">
                  {alertSaving ? 'Saving...' : 'Create Alert'}
                </button>
                <button onClick={() => setShowAlertForm(false)} className="px-4 py-2 border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg text-sm transition-colors">
                  Cancel
                </button>
              </div>
            </div>
          )}

          {alerts.length === 0 ? (
            <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-gray-400 text-sm">
              No alerts configured yet. Create one above.
            </div>
          ) : (
            <div className="space-y-2">
              {alerts.map(alert => (
                <div key={alert.id} className="rounded-lg border border-gray-200 bg-white p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {alert.is_active
                      ? <CheckCircle size={16} className="text-green-500 shrink-0" />
                      : <XCircle size={16} className="text-gray-400 shrink-0" />
                    }
                    <div>
                      <p className="text-sm font-medium text-gray-900">{alert.name}</p>
                      <p className="text-xs text-gray-500">
                        {alert.metric} {alert.condition === 'gt' ? '>' : '<'} {alert.threshold} over {alert.window_minutes}m · {alert.notify_method}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1 text-xs text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                      <AlertTriangle size={11} />Monitoring coming soon
                    </span>
                    <button onClick={() => handleDeleteAlert(alert.id)} className="text-gray-400 hover:text-red-500 transition-colors">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      </div>
    </AgentPageShell>
  )
}
