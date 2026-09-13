import { afterEach, expect, it, vi } from 'vitest'
import { createStreamTextBatcher } from './streamTextBatcher'

afterEach(() => vi.unstubAllGlobals())

it('shows first text immediately and coalesces later updates without losing text', () => {
  let nextFrame: FrameRequestCallback = () => {}
  vi.stubGlobal('requestAnimationFrame', vi.fn(callback => { nextFrame = callback; return 1 }))
  vi.stubGlobal('cancelAnimationFrame', vi.fn())
  const commit = vi.fn()
  const batch = createStreamTextBatcher(commit)
  batch.push('a')
  expect(commit).toHaveBeenLastCalledWith('a')
  batch.push('ab')
  batch.push('abc')
  expect(commit).toHaveBeenCalledTimes(1)
  nextFrame(0)
  expect(commit).toHaveBeenLastCalledWith('abc')
  expect(commit).toHaveBeenCalledTimes(2)
})

it('flushes before terminal events and cancellation prevents stale writes', () => {
  vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1))
  vi.stubGlobal('cancelAnimationFrame', vi.fn())
  const commit = vi.fn()
  const batch = createStreamTextBatcher(commit)
  batch.push('a')
  batch.push('ab')
  batch.flush()
  expect(commit).toHaveBeenLastCalledWith('ab')
  batch.push('abc')
  batch.cancel()
  batch.flush()
  expect(commit).toHaveBeenCalledTimes(2)
})
