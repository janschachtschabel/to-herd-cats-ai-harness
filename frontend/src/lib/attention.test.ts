import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import {
  IDLE_AFTER_MS,
  TOUCH_EVERY_MS,
  UNATTENDED_HEADER,
  isUnattended,
  markRequest,
  resetAttention,
  touchDue,
  watchInput,
} from './attention'

const T0 = 1_800_000_000_000

function request(): Request {
  return new Request('http://localhost/api/conversations/unread')
}

describe('attention', () => {
  beforeEach(() => resetAttention(T0))

  it('marks a request sent after more than a minute without input', () => {
    expect(markRequest(request(), T0 + IDLE_AFTER_MS).headers.get(UNATTENDED_HEADER)).toBeNull()
    const late = markRequest(request(), T0 + IDLE_AFTER_MS + 1)
    expect(late.headers.get(UNATTENDED_HEADER)).toBe('1')
  })

  it('counts pointer, key, wheel, touch, focus and the tab becoming visible as input', () => {
    const stop = watchInput(window)
    try {
      const events: [EventTarget, Event][] = [
        [window, new Event('pointerdown')],
        [window, new KeyboardEvent('keydown', { key: 'a' })],
        [window, new Event('wheel')],
        [window, new Event('touchstart')],
        [window, new FocusEvent('focus')],
        [document, new Event('visibilitychange')],
      ]
      for (const [target, event] of events) {
        resetAttention(T0)
        vi.spyOn(Date, 'now').mockReturnValue(T0 + 10 * IDLE_AFTER_MS)
        expect(isUnattended()).toBe(true)
        target.dispatchEvent(event)
        expect(isUnattended(), event.type).toBe(false)
        vi.restoreAllMocks()
      }
    } finally {
      stop()
    }
  })

  it('stops listening after the cleanup', () => {
    watchInput(window)()
    window.dispatchEvent(new Event('pointerdown'))
    expect(isUnattended(T0 + 2 * IDLE_AFTER_MS)).toBe(true)
  })

  it('wants a touch only while the person is here and nothing counted for 5 minutes', () => {
    const at = T0 + TOUCH_EVERY_MS
    expect(touchDue(at)).toBe(false) // nobody gave input for 5 minutes
    resetAttention(T0)
    markRequest(request(), T0 + 30_000) // counted: the person clicked
    expect(touchDue(T0 + 30_000 + TOUCH_EVERY_MS - 1)).toBe(false)
    // Typing in the live editor: input, but no request.
    const typing = watchInput(window)
    try {
      vi.spyOn(Date, 'now').mockReturnValue(T0 + 30_000 + TOUCH_EVERY_MS)
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'x' }))
      expect(touchDue()).toBe(true)
      markRequest(request()) // the touch itself counts
      expect(touchDue()).toBe(false)
    } finally {
      vi.restoreAllMocks()
      typing()
    }
  })
})

describe('the API client', () => {
  afterEach(() => vi.restoreAllMocks())

  it('sends the mark on a request nobody caused, and none on one somebody did', async () => {
    const sent: Request[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      sent.push(input as Request)
      return Promise.resolve(new Response('{}', { status: 200 }))
    })
    resetAttention(Date.now() - 2 * IDLE_AFTER_MS)
    await api.GET('/api/conversations/unread', { params: { query: { limit: 100 } } })
    resetAttention(Date.now())
    await api.GET('/api/conversations/unread', { params: { query: { limit: 100 } } })
    expect(sent.map((r) => r.headers.get(UNATTENDED_HEADER))).toEqual(['1', null])
  })
})
