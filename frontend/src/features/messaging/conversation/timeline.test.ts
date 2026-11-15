import { describe, expect, test } from 'vitest'
import { makeMessage } from '@/test/messaging'
import type { PendingMessage } from './pending'
import { buildTimeline, firstUnreadId } from './timeline'

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
