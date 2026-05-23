'use client'

import dynamic from 'next/dynamic'
import type { ChartData } from '../ChartRenderer'

const Plot = dynamic(() => import('react-plotly.js') as any, { ssr: false }) as any  

export function PlotlyRenderer({ chart }: { chart: ChartData }) {
  const d = chart.data as { data?: object[]; layout?: object }
  return (
    <Plot
      data={d?.data ?? []}
      layout={{
        autosize: true,
        margin: { l: 50, r: 30, t: 10, b: 50 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { size: 12, family: 'inherit' },
        showlegend: true,
        ...d?.layout,
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%', height: '100%' }}
      useResizeHandler
    />
  )
}
