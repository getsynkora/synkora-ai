'use client'

import { useEffect, useRef, useState } from 'react'
import type { ChartData } from '../ChartRenderer'
import { loadPlotly, plotlyFamily, type PlotlyBundle } from './plotlyBundles'

export function PlotlyRenderer({ chart }: { chart: ChartData }) {
  const container = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const parent = container.current
    if (!parent) return
    const node = document.createElement('div')
    node.style.width = '100%'
    node.style.height = '100%'
    parent.appendChild(node)
    let disposed = false
    let plotly: PlotlyBundle | undefined
    let observer: ResizeObserver | undefined
    setError(null)

    async function render() {
      const d = chart.data as { data?: object[]; layout?: object }
      const data = d.data ?? []
      const bundle = await loadPlotly(plotlyFamily(data, chart.chart_type))
      if (disposed) return
      plotly = bundle
      await bundle.react(node, data, {
        autosize: true,
        margin: { l: 50, r: 30, t: 10, b: 50 },
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { size: 12, family: 'inherit' },
        showlegend: true,
        ...d.layout,
      }, { displayModeBar: false, responsive: true })
      if (disposed) {
        bundle.purge(node)
        return
      }
      observer = new ResizeObserver(() => { void bundle.Plots.resize(node).catch(() => {}) })
      observer.observe(parent!)
    }
    void render().catch(() => {
      if (!disposed) setError('Unable to display this chart.')
    })
    return () => {
      disposed = true
      observer?.disconnect()
      plotly?.purge(node)
      node.remove()
    }
  }, [chart.data, chart.chart_type])

  return <>
    {error && <p role="alert">{error}</p>}
    <div ref={container} style={{ width: '100%', height: '100%' }} />
  </>
}
