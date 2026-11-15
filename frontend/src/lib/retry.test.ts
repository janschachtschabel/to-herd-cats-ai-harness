import { describe, expect, it, vi } from 'vitest'
import { api, unwrap } from './api'
import { MAX_RETRY_WAIT_MS, retryWaitMs, retryingOnConflict } from './retry'

function answer(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

const RETRY = { error: { code: 'conflict.retry', message: 'again', trace_id: 'x' } }

describe('retryingOnConflict', () => {
  it('sends a request once more after the Retry-After the backend names', async () => {
    const send = vi
      .fn<(request: Request) => Promise<Response>>()
      .mockResolvedValueOnce(answer(409, RETRY, { 'Retry-After': '1' }))
      .mockResolvedValueOnce(answer(200, { ok: true }))
    const wait = vi.fn(() => Promise.resolve())
    const request = new Request('http://localhost/api/tickets/1', {
      method: 'PATCH',
      body: JSON.stringify({ version: 3, assignee: null }),
    })
    const response = await retryingOnConflict(send, wait)(request)
    expect(response.status).toBe(200)
    expect(wait).toHaveBeenCalledWith(1000)
    expect(send).toHaveBeenCalledTimes(2)
    const resent = send.mock.calls[1]?.[0]
    expect(await resent?.text()).toBe('{"version":3,"assignee":null}')
  })

  it('tries only once more, and never for another conflict', async () => {
    const twice = vi.fn(() => Promise.resolve(answer(409, RETRY)))
    const wait = vi.fn(() => Promise.resolve())
    const first = await retryingOnConflict(twice, wait)(new Request('http://localhost/api/x'))
    expect(first.status).toBe(409)
    expect(twice).toHaveBeenCalledTimes(2)
    const stale = { error: { code: 'ticket.version_conflict', message: 'm', trace_id: 'x' } }
    const other = vi.fn(() => Promise.resolve(answer(409, stale)))
    await retryingOnConflict(other, wait)(new Request('http://localhost/api/x'))
    expect(other).toHaveBeenCalledTimes(1)
  })

  it('waits at most two seconds, and one without a usable header', () => {
    expect(retryWaitMs('30')).toBe(MAX_RETRY_WAIT_MS)
    expect(retryWaitMs('0.5')).toBe(500)
    expect(retryWaitMs(null)).toBe(1000)
    expect(retryWaitMs('soon')).toBe(1000)
  })

  it('is what the API client does', async () => {
    vi.useFakeTimers()
    const fetchMock = vi
      .fn<(request: Request) => Promise<Response>>()
      .mockResolvedValueOnce(answer(409, RETRY, { 'Retry-After': '1' }))
      .mockResolvedValueOnce(answer(200, { id: 'p1' }))
    vi.stubGlobal('fetch', fetchMock)
    try {
      const pending = api.GET('/api/auth/me')
      await vi.advanceTimersByTimeAsync(1000)
      expect(unwrap(await pending)).toEqual({ id: 'p1' })
      expect(fetchMock).toHaveBeenCalledTimes(2)
    } finally {
      vi.unstubAllGlobals()
      vi.useRealTimers()
    }
  })
})
