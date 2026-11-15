import { describe, expect, test } from 'vitest'
import { makeMessage } from '@/test/messaging'
import type { PendingMessage } from './pending'
import { buildTimeline, firstAfterPosition, firstUnreadId } from './timeline'

const me = { type: 'user' as const, id: 'me', name: 'Mia' }

describe('timeline', () => {
  test('the first unread is the n-th countable message from the newest', () => {
    const newest = [
      makeMessage({ id: 'm5' }),
      makeMessage({ id: 'm4', author: me }),
      makeMessage({ id: 'm3', deleted_at: '2026-11-13T10:00:00Z' }),
      makeMessage({ id: 'm2' }),
      makeMessage({ id: 'm1' }),
    ]
    expect(firstUnreadId(newest, 2, 'me')).toBe('m2')
    expect(firstUnreadId(newest, 0, 'me')).toBeNull()
    expect(firstUnreadId(newest, 9, 'me')).toBe('m1')
  })

  test('after a read position, the oldest countable message newer than it is the first unread', () => {
    const newest = [
      makeMessage({ id: 'm5', created_at: '2026-11-13T09:05:00Z' }),
      makeMessage({ id: 'm4', created_at: '2026-11-13T09:04:00Z', author: me }),
      makeMessage({ id: 'm3', created_at: '2026-11-13T09:03:00Z' }),
      makeMessage({ id: 'm2', created_at: '2026-11-13T09:02:00Z' }),
      makeMessage({ id: 'm1', created_at: '2026-11-13T09:01:00Z' }),
    ]
    const at = (id: string, time: string) => ({ id, at: time })
    expect(firstAfterPosition(newest, at('m2', '2026-11-13T09:02:00Z'), 'me')).toBe('m3')
    expect(firstAfterPosition(newest, at('m5', '2026-11-13T09:05:00Z'), 'me')).toBeNull()
    // One's own message after it does not count.
    expect(firstAfterPosition(newest, at('m3', '2026-11-13T09:03:00Z'), 'me')).toBe('m5')
    // The read message is older than everything loaded: the oldest loaded that counts.
    expect(firstAfterPosition(newest, at('m0', '2026-11-13T08:00:00Z'), 'me')).toBe('m1')
    // The read message is gone from the list (deleted): its time still places the marker.
    expect(firstAfterPosition(newest, at('gone', '2026-11-13T09:03:30Z'), 'me')).toBe('m5')
  })

  test('day separators, the marker, and pending messages the server does not have yet', () => {
    const newest = [
      makeMessage({ id: 'b', created_at: '2026-11-13T12:00:00', client_id: 'k1' }),
      makeMessage({ id: 'a', created_at: '2026-11-12T12:00:00' }),
    ]
    const pending = (clientId: string): PendingMessage => ({
      clientId,
      conversationId: 'c',
      parentId: null,
      body: 'x',
      mentions: [],
      status: 'sending',
      error: null,
      createdAt: '2026-11-13T12:05:00',
    })
    const rows = buildTimeline(newest, [pending('k1'), pending('k2')], 'b')
    expect(rows.map((r) => r.key)).toEqual([
      'day-2026-11-12',
      'a',
      'day-2026-11-13',
      'new',
      'b',
      'pending-k2',
    ])
  })

  test('a fresh start sits before the first message after it, or at the end', () => {
    const newest = [
      makeMessage({ id: 'c', created_at: '2026-11-13T12:10:00Z' }),
      makeMessage({ id: 'b', created_at: '2026-11-13T12:05:00Z' }),
      makeMessage({ id: 'a', created_at: '2026-11-13T12:00:00Z' }),
    ]
    const keys = (fresh: string | null) =>
      buildTimeline(newest, [], null, fresh)
        .filter((r) => r.kind !== 'day')
        .map((r) => r.key)
    expect(keys('2026-11-13T12:03:00Z')).toEqual(['a', 'fresh', 'b', 'c'])
    expect(keys('2026-11-13T12:30:00Z')).toEqual(['a', 'b', 'c', 'fresh'])
    expect(keys(null)).toEqual(['a', 'b', 'c'])
  })
})
