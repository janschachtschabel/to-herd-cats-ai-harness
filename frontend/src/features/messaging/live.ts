import { useQueryClient, type InfiniteData, type QueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo } from 'react'
import type { Conversation, Page } from '@/lib/api'
import { agentKeys } from '@/features/agents/keys'
import { noteRunProgress } from '@/features/agents/live'
import { ticketKeys } from '@/features/tickets/keys'
import { sprintEventKeys, ticketEventKeys } from '@/features/tickets/live'
import { useLive, type LiveEvent } from '@/lib/live'
import { activityKeys, messagingKeys } from './keys'

type Key = readonly unknown[]

/** How long events are gathered before their queries are refreshed: a burst of
 *  messages refreshes each query once, not once per message. */
export const COALESCE_MS = 250

/** Every query (`access.changed`: what one may see has changed). */
const EVERYTHING: Key = []

function isKnownChannel(queryClient: QueryClient, conversationId: string): boolean {
  const data = queryClient.getQueryData<InfiniteData<Page<Conversation>>>(messagingKeys.channels)
  return data?.pages?.some((page) => page.items.some((c) => c.id === conversationId)) ?? false
}

/** Which queries an event makes stale. Content is never taken from the event: the
 *  marked queries refetch through the API, which checks the rights again. */
export function keysFor(queryClient: QueryClient, event: LiveEvent): Key[] {
  const conversation = event.conversationId
  switch (event.type) {
    case 'resync':
      return [messagingKeys.all, activityKeys.all, ticketKeys.all, agentKeys.runs]
    case 'access.changed':
      // Reload whatever is shown; what is gone answers 404 and is dropped.
      return [EVERYTHING]
    case 'message.created':
    case 'message.updated':
    case 'message.deleted': {
      if (!conversation) return []
      const keys: Key[] = [messagingKeys.messages(conversation), messagingKeys.unread]
      if (event.parentId) keys.push(messagingKeys.replies(conversation, event.parentId))
      keys.push(messagingKeys.message(conversation))
      // A direct message moves up its list (or appears: someone wrote to me first).
      if (!isKnownChannel(queryClient, conversation)) keys.push(messagingKeys.dms)
      // An agent's answer or stop notice: the run shown with progress is done.
      if (event.type === 'message.created') keys.push(agentKeys.runs)
      return keys
    }
    case 'reaction.changed':
      if (!conversation) return []
      return [
        messagingKeys.messages(conversation),
        messagingKeys.replies(conversation),
        messagingKeys.message(conversation),
      ]
    case 'conversation.read':
      return [messagingKeys.unread]
    case 'channel.changed':
      return conversation
        ? [messagingKeys.channels, messagingKeys.conversation(conversation)]
        : [messagingKeys.channels]
    case 'dm.inspected':
      return conversation ? [messagingKeys.conversation(conversation)] : []
    case 'notification.created':
    case 'activity.changed':
      return [activityKeys.all]
    case 'ticket.created':
    case 'ticket.updated':
      // Its timeline entries arrive as `message.created` in the ticket's thread.
      return ticketEventKeys(queryClient, event.ticketId, event.spaceId)
    case 'sprint.changed':
      return sprintEventKeys(queryClient, event.spaceId)
    case 'run.progress':
      return event.runId ? [agentKeys.run(event.runId)] : []
  }
}

function refresh(queryClient: QueryClient, keys: Iterable<Key>): void {
  for (const key of keys) void queryClient.invalidateQueries({ queryKey: [...key] })
}

/** Marks an event's queries stale at once. */
export function invalidateFor(queryClient: QueryClient, event: LiveEvent): void {
  refresh(queryClient, keysFor(queryClient, event))
}

/** Gathers the events of COALESCE_MS and then refreshes each of their queries once. */
export function createCoalescer(queryClient: QueryClient, windowMs = COALESCE_MS) {
  const waiting = new Map<string, Key>()
  let timer: ReturnType<typeof setTimeout> | undefined
  const flush = () => {
    timer = undefined
    const keys = [...waiting.values()]
    waiting.clear()
    refresh(queryClient, keys)
  }
  return {
    add(event: LiveEvent): void {
      for (const key of keysFor(queryClient, event)) waiting.set(JSON.stringify(key), key)
      if (timer === undefined && waiting.size > 0) timer = setTimeout(flush, windowMs)
    },
    stop(): void {
      clearTimeout(timer)
      timer = undefined
      waiting.clear()
    },
  }
}

/** This tab's live updates: one stream, mounted once by the shell. */
export function useLiveUpdates(): void {
  const queryClient = useQueryClient()
  const coalescer = useMemo(() => createCoalescer(queryClient), [queryClient])
  useEffect(() => () => coalescer.stop(), [coalescer])
  const onEvent = useCallback(
    (event: LiveEvent) => {
      noteRunProgress(queryClient, event)
      coalescer.add(event)
    },
    [coalescer, queryClient],
  )
  useLive(onEvent)
}
