import { renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { type LiveEvent, parseLiveEvent, useLive } from './live'

/** A stand-in for the browser's EventSource that tests drive by hand. */
class FakeEventSource {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSED = 2
  static all: FakeEventSource[] = []
  readyState = FakeEventSource.CONNECTING
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  private listeners = new Map<string, ((event: MessageEvent) => void)[]>()

  readonly url: string

  constructor(url: string) {
    this.url = url
    FakeEventSource.all.push(this)
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener])
  }

  close() {
    this.readyState = FakeEventSource.CLOSED
  }

  open() {
    this.readyState = FakeEventSource.OPEN
    this.onopen?.()
  }

  fail(closed: boolean) {
    this.readyState = closed ? FakeEventSource.CLOSED : FakeEventSource.CONNECTING
    this.onerror?.()
  }

  emit(type: string, data: string) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data }))
    }
  }
}

beforeEach(() => {
  FakeEventSource.all = []
  vi.stubGlobal('EventSource', FakeEventSource)
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 401 }))
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('live stream', () => {
  test('one stream per mount; events arrive as ids only', () => {
    const seen: LiveEvent[] = []
    const { unmount } = renderHook(() => useLive((event) => seen.push(event)))
    expect(FakeEventSource.all).toHaveLength(1)
    const source = FakeEventSource.all[0]!
    source.open()
    source.emit(
      'message.created',
      '{"conversation_id":"c1","message_id":"m1","parent_id":null,"body_md":"x"}',
    )
    expect(seen).toEqual([
      {
        type: 'message.created',
        conversationId: 'c1',
        messageId: 'm1',
        parentId: null,
        ticketId: null,
        spaceId: null,
      },
    ])
    unmount()
    expect(source.readyState).toBe(FakeEventSource.CLOSED)
  })

  test('after an interruption the reopened stream starts with a resync', () => {
    const seen: string[] = []
    renderHook(() => useLive((event) => seen.push(event.type)))
    const source = FakeEventSource.all[0]!
    source.open()
    source.fail(false) // the browser reconnects on its own
    source.open()
    expect(seen).toEqual(['resync'])
  })

  test('a refused stream is opened again after a wait, then resyncs', () => {
    vi.useFakeTimers()
    const seen: string[] = []
    renderHook(() => useLive((event) => seen.push(event.type)))
    FakeEventSource.all[0]!.fail(true)
    expect(FakeEventSource.all).toHaveLength(1)
    vi.advanceTimersByTime(5_000)
    expect(FakeEventSource.all).toHaveLength(2)
    FakeEventSource.all[1]!.open()
    expect(seen).toEqual(['resync'])
  })

  test('unreadable data is dropped', () => {
    expect(parseLiveEvent('message.created', 'not json')).toBeNull()
    expect(parseLiveEvent('resync', '{}')).toEqual({
      type: 'resync',
      conversationId: null,
      messageId: null,
      parentId: null,
      ticketId: null,
      spaceId: null,
    })
  })

  test('a sprint event carries its space (plan M4b)', () => {
    expect(parseLiveEvent('sprint.changed', '{"space_id":"s1","sprint_id":"r1"}')).toMatchObject({
      type: 'sprint.changed',
      spaceId: 's1',
      ticketId: null,
    })
  })

  test('ticket events carry the ticket, its space and its thread', () => {
    expect(
      parseLiveEvent(
        'ticket.updated',
        '{"conversation_id":"c1","message_id":null,"parent_id":null,"ticket_id":"t1","space_id":"s1"}',
      ),
    ).toEqual({
      type: 'ticket.updated',
      conversationId: 'c1',
      messageId: null,
      parentId: null,
      ticketId: 't1',
      spaceId: 's1',
    })
  })

  test("an agent run's progress carries the run and its step (plan M5), nothing else", () => {
    expect(
      parseLiveEvent('run.progress', '{"conversation_id":"c1","run_id":"r1","step":2}'),
    ).toEqual({
      type: 'run.progress',
      conversationId: 'c1',
      messageId: null,
      parentId: null,
      ticketId: null,
      spaceId: null,
      runId: 'r1',
      step: 2,
    })
    expect(
      parseLiveEvent('run.progress', '{"conversation_id":"c1","run_id":"r1","step":"x"}'),
    ).toMatchObject({ runId: 'r1', step: null })
  })
})
