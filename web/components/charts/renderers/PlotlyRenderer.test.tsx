import { act, render, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PlotlyRenderer } from './PlotlyRenderer'
import { loadPlotly, plotlyFamily, type PlotlyBundle } from './plotlyBundles'
import type { ChartData } from '../ChartRenderer'

vi.mock('./plotlyBundles', async importOriginal => ({
  ...await importOriginal<typeof import('./plotlyBundles')>(), loadPlotly: vi.fn(),
}))
afterEach(() => vi.clearAllMocks())

const chart = (type: string): ChartData => ({ id:'1', title:'Test', chart_type:type, library:'plotly', data:{data:[{type,x:[1,2],y:[3,4]}]}, config:{}, created_at:'' })

describe('supported Plotly families', () => {
  it.each(['heatmap', 'box', 'violin'])('retains %s', type => {
    expect(plotlyFamily([{type}], type)).toBe('cartesian')
  })
  it.each(['candlestick', 'waterfall'])('retains %s', type => {
    expect(plotlyFamily([{type}], type)).toBe('finance')
  })
  it.each(['scattermap', 'choroplethmap', 'densitymap', 'scattermapbox'])('rejects %s without loading map code', type => {
    expect(() => plotlyFamily([{type}], type)).toThrow('unsupported')
  })
})

it('renders supported data and purges the chart on unmount', async () => {
  const bundle = {react:vi.fn().mockResolvedValue(undefined), purge:vi.fn(), Plots:{resize:vi.fn().mockResolvedValue(undefined)}}
  vi.mocked(loadPlotly).mockResolvedValue(bundle)
  const disconnect = vi.fn()
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect = disconnect })
  const view = render(<PlotlyRenderer chart={chart('heatmap')} />)
  await waitFor(() => expect(bundle.react).toHaveBeenCalledOnce())
  expect(loadPlotly).toHaveBeenCalledWith('cartesian')
  expect(bundle.react.mock.calls[0][1]).toEqual([{type:'heatmap',x:[1,2],y:[3,4]}])
  view.unmount()
  expect(bundle.purge).toHaveBeenCalledOnce()
  expect(disconnect).toHaveBeenCalledOnce()
  vi.unstubAllGlobals()
})

it('does not paint after unmount while a bundle is loading', async () => {
  let resolve!: (bundle: PlotlyBundle) => void
  vi.mocked(loadPlotly).mockReturnValue(new Promise(done => {resolve = done}))
  const bundle = {react:vi.fn().mockResolvedValue(undefined),purge:vi.fn(),Plots:{resize:vi.fn().mockResolvedValue(undefined)}}
  const view = render(<PlotlyRenderer chart={chart('waterfall')} />)
  view.unmount()
  await act(async () => resolve(bundle))
  expect(bundle.react).not.toHaveBeenCalled()
})
