import { QueryClient } from '@tanstack/react-query'
import { describe, expect, test } from 'vitest'
import type { LiveEvent } from '@/lib/live'
import { activityKeys, messagingKeys } from './keys'
import { invalidateFor } from './live'

const KEYS = {
  channels: messagingKeys.channels,
  dms: messagingKeys.dms,
  unread: messagingKeys.unread,
  conversationA: messagingKeys.conversation('a'),
  messagesA: [...messagingKeys.messages('a'), { includeSystem: true }],
  messagesB: [...messagingKeys.messages('b'), { includeSystem: true }],
  repliesA: messagingKeys.replies('a', 'p'),
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
    ])
  })

  test('the other events refresh only what they touch', () => {
    expect(staleAfter({ type: 'reaction.changed', conversationId: 'a' })).toEqual([
      'messagesA',
      'repliesA',
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
})
