import {
  infiniteQueryOptions,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type InfiniteData,
  type QueryClient,
} from '@tanstack/react-query'
import { useCallback } from 'react'
import { api, ApiError, unwrap, type Message, type MessageWrite, type Page } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { messagingKeys } from '../keys'
import {
  addPending,
  getPending,
  removePending,
  updatePending,
  type PendingMessage,
} from './pending'

const PAGE_SIZE = 50

/** Top-level messages, newest first; each further page is older. */
export const messagesQuery = (conversationId: string, includeSystem = true) =>
  infiniteQueryOptions({
    queryKey: [...messagingKeys.messages(conversationId), { includeSystem }],
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET('/api/conversations/{conversation_id}/messages', {
          params: {
            path: { conversation_id: conversationId },
            query: { cursor: pageParam, limit: PAGE_SIZE, include_system: includeSystem },
          },
        }),
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last: Page<Message>) => last.next_cursor ?? undefined,
  })

export function useMessages(conversationId: string, includeSystem = true) {
  const query = useInfiniteQuery(messagesQuery(conversationId, includeSystem))
  return {
    messages: query.data?.pages.flatMap((page) => page.items) ?? [],
    loaded: query.isSuccess,
    isPending: query.isPending,
    isError: query.isError,
    error: query.error,
    refetch: () => void query.refetch(),
    hasOlder: query.hasNextPage,
    loadingOlder: query.isFetchingNextPage,
    loadOlder: () => void query.fetchNextPage(),
  }
}

/** A thread's replies, oldest first; each further page is newer. */
export const repliesQuery = (conversationId: string, parentId: string) =>
  pagedQuery(messagingKeys.replies(conversationId, parentId), async (cursor) =>
    unwrap(
      await api.GET('/api/messages/{message_id}/replies', {
        params: { path: { message_id: parentId }, query: { cursor, limit: PAGE_SIZE } },
      }),
    ),
  )

export function useReplies(conversationId: string, parentId: string) {
  return usePaged(repliesQuery(conversationId, parentId))
}

/** One message by id: a thread's parent that is not among the loaded messages (an
 *  older one, a link to a reply). Asked only while `enabled`. */
export function useMessage(conversationId: string, messageId: string, enabled: boolean) {
  return useQuery({
    queryKey: [...messagingKeys.message(conversationId, messageId)],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/messages/{message_id}', {
          params: { path: { message_id: messageId } },
        }),
      ),
    enabled,
  })
}

type Pages = InfiniteData<Page<Message>>

/** Puts a message the server returned into the cached lists at once (no flicker
 *  between the pending entry and the refetch), replacing an older copy. */
function storeMessage(queryClient: QueryClient, message: Message | MessageWrite): void {
  const { not_notified: _, ...plain } = message as MessageWrite
  const replace = (data: Pages | undefined, add: 'first' | 'last' | null): Pages | undefined => {
    if (!data) return data
    const known = data.pages.some((p) => p.items.some((m) => m.id === message.id))
    if (known) {
      return {
        ...data,
        pages: data.pages.map((p) => ({
          ...p,
          items: p.items.map((m) => (m.id === message.id ? plain : m)),
        })),
      }
    }
    if (!add || data.pages.length === 0) return data
    const index = add === 'first' ? 0 : data.pages.length - 1
    return {
      ...data,
      pages: data.pages.map((p, i) =>
        i !== index
          ? p
          : { ...p, items: add === 'first' ? [plain, ...p.items] : [...p.items, plain] },
      ),
    }
  }
  const c = message.conversation_id
  if (message.parent_id) {
    queryClient.setQueriesData<Pages>(
      { queryKey: [...messagingKeys.replies(c, message.parent_id)] },
      (data) => replace(data, 'last'),
    )
  } else {
    queryClient.setQueriesData<Pages>({ queryKey: [...messagingKeys.messages(c)] }, (data) =>
      replace(data, 'first'),
    )
  }
}

function refresh(queryClient: QueryClient, conversationId: string, parentId: string | null) {
  void queryClient.invalidateQueries({ queryKey: [...messagingKeys.messages(conversationId)] })
  if (parentId) {
    void queryClient.invalidateQueries({
      queryKey: [...messagingKeys.replies(conversationId, parentId)],
    })
  }
}

/** Sending is optimistic: the message shows at once as pending, with the client's
 *  key; a failure keeps it, marked, for "send again" (same key: never twice). */
export function useSendMessage(conversationId: string, parentId: string | null) {
  const queryClient = useQueryClient()
  const deliver = useCallback(
    async (message: PendingMessage): Promise<MessageWrite | null> => {
      updatePending(message.clientId, { status: 'sending', error: null })
      try {
        const written = unwrap(
          await api.POST('/api/conversations/{conversation_id}/messages', {
            params: { path: { conversation_id: conversationId } },
            body: {
              body_md: message.body,
              parent_id: message.parentId,
              client_id: message.clientId,
              mentions: message.mentions,
            },
          }),
        )
        storeMessage(queryClient, written)
        removePending(message.clientId)
        refresh(queryClient, conversationId, parentId)
        void queryClient.invalidateQueries({ queryKey: [...messagingKeys.dms] })
        return written
      } catch (error) {
        updatePending(message.clientId, { status: 'failed', error })
        // Archived meanwhile or no longer visible: the view learns it from a fresh look.
        if (error instanceof ApiError && (error.status === 404 || error.status === 409)) {
          void queryClient.invalidateQueries({
            queryKey: [...messagingKeys.conversation(conversationId)],
          })
        }
        return null
      }
    },
    [queryClient, conversationId, parentId],
  )

  const send = useCallback(
    (body: string, mentions: string[]) => {
      const message: PendingMessage = {
        clientId: crypto.randomUUID(),
        conversationId,
        parentId,
        body,
        mentions,
        status: 'sending',
        error: null,
        createdAt: new Date().toISOString(),
      }
      addPending(message)
      return deliver(message)
    },
    [conversationId, parentId, deliver],
  )

  const retry = useCallback(
    (clientId: string) => {
      const message = getPending(clientId)
      return message ? deliver(message) : Promise.resolve(null)
    },
    [deliver],
  )

  return { send, retry, discard: removePending }
}

export function useEditMessage(message: Message) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: { body_md: string; mentions: string[] }) =>
      unwrap(
        await api.PATCH('/api/messages/{message_id}', {
          params: { path: { message_id: message.id } },
          body,
        }),
      ),
    onSuccess: (written) => {
      storeMessage(queryClient, written)
      refresh(queryClient, message.conversation_id, message.parent_id)
    },
  })
}

export function useDeleteMessage(message: Message) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.DELETE('/api/messages/{message_id}', {
          params: { path: { message_id: message.id } },
        }),
      ),
    onSuccess: () => refresh(queryClient, message.conversation_id, message.parent_id),
  })
}

/** Adds my reaction with `emoji`, or takes it back if I reacted with it already. */
export function useToggleReaction(message: Message) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (emoji: string) => {
      const mine = message.reactions.some((r) => r.emoji === emoji && r.mine)
      const params = { params: { path: { message_id: message.id, emoji } } }
      return unwrap(
        mine
          ? await api.DELETE('/api/messages/{message_id}/reactions/{emoji}', params)
          : await api.PUT('/api/messages/{message_id}/reactions/{emoji}', params),
      )
    },
    onSuccess: (reactions) => storeMessage(queryClient, { ...message, reactions }),
  })
}
