import { useQueryClient, type InfiniteData, type QueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'
import type { Conversation, Page } from '@/lib/api'
import { useLive, type LiveEvent } from '@/lib/live'
import { activityKeys, messagingKeys } from './keys'

function isKnownChannel(queryClient: QueryClient, conversationId: string): boolean {
  const data = queryClient.getQueryData<InfiniteData<Page<Conversation>>>(messagingKeys.channels)
  return data?.pages?.some((page) => page.items.some((c) => c.id === conversationId)) ?? false
}

/** Which queries an event makes stale. Content is never taken from the event: the
 *  marked queries refetch through the API, which checks the rights again. */
export function invalidateFor(queryClient: QueryClient, event: LiveEvent): void {
  const stale = (queryKey: readonly unknown[]) =>
    void queryClient.invalidateQueries({ queryKey: [...queryKey] })
  const conversation = event.conversationId
  switch (event.type) {
    case 'resync':
      stale(messagingKeys.all)
      stale(activityKeys.all)
      return
    case 'message.created':
    case 'message.updated':
    case 'message.deleted':
      if (!conversation) return
      stale(messagingKeys.messages(conversation))
      if (event.parentId) stale(messagingKeys.replies(conversation, event.parentId))
      stale(messagingKeys.unread)
      // A direct message moves up its list (or appears: someone wrote to me first).
      if (!isKnownChannel(queryClient, conversation)) stale(messagingKeys.dms)
      return
    case 'reaction.changed':
      if (!conversation) return
      stale(messagingKeys.messages(conversation))
      stale(messagingKeys.replies(conversation))
      return
    case 'conversation.read':
      stale(messagingKeys.unread)
      return
    case 'channel.changed':
      stale(messagingKeys.channels)
      if (conversation) stale(messagingKeys.conversation(conversation))
      return
    case 'notification.created':
    case 'activity.changed':
      stale(activityKeys.all)
      return
  }
}

/** This tab's live updates: one stream, mounted once by the shell. */
export function useLiveUpdates(): void {
  const queryClient = useQueryClient()
  const onEvent = useCallback(
    (event: LiveEvent) => invalidateFor(queryClient, event),
    [queryClient],
  )
  useLive(onEvent)
}
