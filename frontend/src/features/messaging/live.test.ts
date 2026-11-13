import { QueryClient } from '@tanstack/react-query'
import { afterEach, describe, expect, test, vi } from 'vitest'
import type { LiveEvent } from '@/lib/live'
import { activityKeys, messagingKeys } from './keys'
import { COALESCE_MS, createCoalescer, invalidateFor } from './live'

const KEYS = {
  channels: messagingKeys.channels,
  dms: messagingKeys.dms,
  unread: messagingKeys.unread,
  conversationA: messagingKeys.conversation('a'),
  messagesA: [...messagingKeys.messages('a'), { includeSystem: true }],
  messagesB: [...messagingKeys.messages('b'), { includeSystem: true }],
  repliesA: messagingKeys.replies('a', 'p'),
  messageA: messagingKeys.message('a', 'p'),
  pageThread: messagingKeys.pageThread('page'),
  activity: activityKeys.list(false),
  activityCount: activityKeys.count,
  spaces: ['spaces', 'sidebar'],
  wiki: ['wiki', 'page', 'x'],
}

/** A client holding every key above, fresh; returns which keys an event made stale. */
function staleAfter(event: Partial<LiveEvent> & Pick<LiveEvent, 'type'>): string[] {
  const client = new QueryClient()
  for (const key of Object.values(KEYS)) client.setQueryData(key, { items: [] })
  invalidateFor(client, { conversationId: null, messageId: null, parentId: null, ...event })
  return Object.entries(KEYS)
    .filter(([, key]) => client.getQueryState(key)?.isInvalidated)
    .map(([name]) => name)
}

describe('live invalidation', () => {
  test('resync refreshes every conversation, counter and activity query, nothing else', () => {
    expect(staleAfter({ type: 'resync' })).toEqual([
      'channels',
      'dms',
      'unread',
      'conversationA',
      'messagesA',
      'messagesB',
      'repliesA',
      'messageA',
      'pageThread',
      'activity',
      'activityCount',
    ])
  })

  test('a message refreshes its conversation (and thread), the counters, the DM list', () => {
    expect(staleAfter({ type: 'message.created', conversationId: 'a', parentId: 'p' })).toEqual([
      'dms',
      'unread',
      'messagesA',
      'repliesA',
      'messageA',
    ])
  })

  test('the other events refresh only what they touch', () => {
    expect(staleAfter({ type: 'reaction.changed', conversationId: 'a' })).toEqual([
      'messagesA',
      'repliesA',
      'messageA',
    ])
    expect(staleAfter({ type: 'conversation.read', conversationId: 'a' })).toEqual(['unread'])
    expect(staleAfter({ type: 'channel.changed', conversationId: 'a' })).toEqual([
      'channels',
      'conversationA',
    ])
    expect(staleAfter({ type: 'notification.created', conversationId: 'a' })).toEqual([
      'activity',
      'activityCount',
    ])
    expect(staleAfter({ type: 'activity.changed' })).toEqual(['activity', 'activityCount'])
  })

  test('a changed access reloads everything shown; an inspection the conversation', () => {
    expect(staleAfter({ type: 'access.changed' })).toEqual(Object.keys(KEYS))
    expect(staleAfter({ type: 'dm.inspected', conversationId: 'a' })).toEqual(['conversationA'])
  })
})

describe('coalescing', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  test('a burst of events refreshes each query once per window', () => {
    vi.useFakeTimers()
    const client = new QueryClient()
    const spy = vi.spyOn(client, 'invalidateQueries').mockResolvedValue()
    const coalescer = createCoalescer(client)
    for (let i = 0; i < 20; i++) {
      coalescer.add({
        type: 'message.created',
        conversationId: 'a',
        messageId: `m${i}`,
        parentId: null,
      })
      coalescer.add({
        type: 'conversation.read',
        conversationId: 'a',
        messageId: null,
        parentId: null,
      })
    }
    expect(spy).not.toHaveBeenCalled()
    vi.advanceTimersByTime(COALESCE_MS)
    const keys = spy.mock.calls.map(([filters]) => JSON.stringify(filters?.queryKey))
    expect(keys.sort()).toEqual(
      [
        messagingKeys.dms,
        messagingKeys.unread,
        messagingKeys.messages('a'),
        messagingKeys.message('a'),
      ]
        .map((key) => JSON.stringify(key))
        .sort(),
    )
    spy.mockClear()
    coalescer.add({
      type: 'activity.changed',
      conversationId: null,
      messageId: null,
      parentId: null,
    })
    vi.advanceTimersByTime(COALESCE_MS)
    expect(spy).toHaveBeenCalledTimes(1) // a new window after the last
    coalescer.add({
      type: 'activity.changed',
      conversationId: null,
      messageId: null,
      parentId: null,
    })
    coalescer.stop()
    vi.advanceTimersByTime(COALESCE_MS)
    expect(spy).toHaveBeenCalledTimes(1) // stopped: nothing more
  })
})
