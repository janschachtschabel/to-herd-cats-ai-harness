/** The query keys of messaging. Every key starts with `messaging`, so a `resync`
 *  can refresh them all; per-conversation keys put the conversation id third, so a
 *  live event can refresh exactly one conversation. */
export const messagingKeys = {
  all: ['messaging'] as const,
  channels: ['messaging', 'channels'] as const,
  dms: ['messaging', 'dms'] as const,
  unread: ['messaging', 'unread'] as const,
  conversation: (id: string) => ['messaging', 'conversation', id] as const,
  /** Top-level messages; the full key adds whether system messages are included. */
  messages: (id: string) => ['messaging', 'messages', id] as const,
  /** A thread's replies; `replies(id)` alone covers every thread of the conversation. */
  replies: (id: string, parentId?: string) =>
    parentId
      ? (['messaging', 'replies', id, parentId] as const)
      : (['messaging', 'replies', id] as const),
  pageThread: (pageId: string) => ['messaging', 'page-thread', pageId] as const,
}

export const activityKeys = {
  all: ['activity'] as const,
  list: (includeDone: boolean) => ['activity', 'list', includeDone] as const,
  count: ['activity', 'count'] as const,
}
