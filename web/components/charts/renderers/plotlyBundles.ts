export interface PlotlyBundle {
  react(node: HTMLElement, data: object[], layout: object, config: object): Promise<unknown>
  purge(node: HTMLElement): void
  Plots: { resize(node: HTMLElement): Promise<unknown> }
}

const cartesian = new Set(['bar', 'box', 'contour', 'heatmap', 'histogram', 'histogram2d', 'histogram2dcontour', 'image', 'pie', 'scatter', 'scatterternary', 'violin'])
const finance = new Set(['bar', 'candlestick', 'funnel', 'funnelarea', 'histogram', 'indicator', 'ohlc', 'pie', 'scatter', 'waterfall'])

export function plotlyFamily(data: object[], chartType: string): 'cartesian' | 'finance' {
  const types = data.map(trace => (trace as {type?: string}).type ?? 'scatter')
  const family = ['candlestick', 'waterfall', 'ohlc'].includes(chartType) || types.some(type => !cartesian.has(type) && finance.has(type)) ? 'finance' : 'cartesian'
  const supported = family === 'finance' ? finance : cartesian
  if (types.some(type => !supported.has(type))) {
    throw new Error('This chart contains an unsupported trace type.')
  }
  return family
}

export async function loadPlotly(family: 'cartesian' | 'finance'): Promise<PlotlyBundle> {
  // Maintained partial distributions cover our chart types without shipping
  // MapLibre or any map rendering code from the full Plotly distribution.
  const bundleModule = family === 'finance'
    ? await import('plotly.js-finance-dist-min')
    : await import('plotly.js-cartesian-dist-min')
  return bundleModule.default
}
