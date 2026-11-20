'use client'

import {
  BarChart,
  Bar as RBar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  Legend as RLegend,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Treemap,
  FunnelChart,
  Funnel,
  LabelList,
  Cell,
  ResponsiveContainer,
} from 'recharts'
import type { ChartData } from '../ChartRenderer'

const CHART_COLORS = [
  '#6366f1', '#8b5cf6', '#06b6d4', '#10b981',
  '#f59e0b', '#ef4444', '#ec4899', '#84cc16',
]

export function RechartsRenderer({ chart }: { chart: ChartData }) {
  const d = chart.data as Record<string, unknown>
  const data = (d?.data as unknown[]) ?? (Array.isArray(d) ? d : [])
  const xKey = (d?.xKey as string) || (d?.nameKey as string) || 'name'
  const yKey = (d?.yKey as string) || (d?.dataKey as string) || 'value'

  switch (chart.chart_type) {
    case 'area':
      return (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data as object[]}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <RTooltip />
            <RLegend />
            <Area type="monotone" dataKey={yKey} stroke="#6366f1" fill="#6366f120" strokeWidth={2} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      )

    case 'stacked_bar': {
      const series = (d?.series as string[]) ?? [yKey]
      return (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data as object[]}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <RTooltip />
            <RLegend />
            {series.map((s, i) => (
              <RBar key={s} dataKey={s} stackId="a" fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )
    }

    case 'radar':
      return (
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data as object[]}>
            <PolarGrid />
            <PolarAngleAxis dataKey={xKey} tick={{ fontSize: 11 }} />
            <PolarRadiusAxis tick={{ fontSize: 10 }} />
            <Radar dataKey={yKey} stroke="#6366f1" fill="#6366f1" fillOpacity={0.4} />
            <RTooltip />
          </RadarChart>
        </ResponsiveContainer>
      )

    case 'treemap':
      return (
        <ResponsiveContainer width="100%" height="100%">
          <Treemap
            data={data as any}
            dataKey={yKey}
            nameKey={xKey}
            aspectRatio={4 / 3}
            stroke="#fff"
            fill="#6366f1"
          />
        </ResponsiveContainer>
      )

    case 'funnel':
      return (
        <ResponsiveContainer width="100%" height="100%">
          <FunnelChart>
            <RTooltip />
            <Funnel dataKey={yKey} data={data as object[]} isAnimationActive>
              {(data as object[]).map((_, i) => (
                <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
              <LabelList position="right" fill="#555" stroke="none" dataKey={xKey} />
            </Funnel>
          </FunnelChart>
        </ResponsiveContainer>
      )

    default:
      return (
        <div className="flex items-center justify-center h-full text-ash text-sm">
          Unsupported type: {chart.chart_type}
        </div>
      )
  }
}
