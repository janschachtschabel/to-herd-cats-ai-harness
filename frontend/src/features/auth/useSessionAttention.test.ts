import { renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resetAttention, TOUCH_EVERY_MS } from '@/lib/attention'
import { TOUCH_CHECK_MS, useSessionAttention } from './useSessionAttention'

function touches(spy: { mock: { calls: unknown[][] } }): number {
  return spy.mock.calls.filter(([input]) => {
    const request = input as Request
    return request.method === 'POST' && new URL(request.url).pathname === '/api/auth/me/touch'
  }).length
}

describe('useSessionAttention', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    resetAttention(Date.now())
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('touches the session while the person types and the app asks nothing', async () => {
    const fetch = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(() => Promise.resolve(new Response(null, { status: 204 })))
    const { unmount } = renderHook(() => useSessionAttention())
    // Five minutes of typing in the live editor, a key every 20 s, no request.
    for (let at = 0; at < TOUCH_EVERY_MS; at += 20_000) {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }))
      await vi.advanceTimersByTimeAsync(20_000)
    }
    await vi.advanceTimersByTimeAsync(TOUCH_CHECK_MS)
    expect(touches(fetch)).toBe(1)
    // Away from the keyboard: no more touches.
    await vi.advanceTimersByTimeAsync(3 * TOUCH_EVERY_MS)
    expect(touches(fetch)).toBe(1)
    unmount()
  })
})
