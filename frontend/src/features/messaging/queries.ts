import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query'
import { useCallback, useMemo } from 'react'
import { api, ApiError, unwrap, type Conversation, type Schemas, type Unread } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { messagingKeys } from './keys'

export const channelsQuery = pagedQuery(messagingKeys.channels, async (cursor) =>
  unwrap(await api.GET('/api/channels', { params: { query: { cursor, limit: 100 } } })),
)

export const dmsQuery = pagedQuery(messagingKeys.dms, async (cursor) =>
  unwrap(await api.GET('/api/dms', { params: { query: { cursor, limit: 50 } } })),
)

// Only conversations with something unread are listed; one page holds the sidebar's.
export const unreadQuery = queryOptions({
  queryKey: messagingKeys.unread,
  queryFn: async () =>
    unwrap(await api.GET('/api/conversations/unread', { params: { query: { limit: 100 } } })),
})

export const conversationQuery = (conversationId: string) =>
  queryOptions({
    queryKey: messagingKeys.conversation(conversationId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/conversations/{conversation_id}', {
          params: { path: { conversation_id: conversationId } },
        }),
      ),
    // Losing access sends no event (the person no longer sees the conversation):
    // look again now and then, so an open view notices and leaves.
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    // Gone is gone: asking again changes nothing.
    retry: (failures, error) =>
      !(error instanceof ApiError && error.status === 404) && failures < 1,
  })

export const pageThreadQuery = (pageId: string) =>
  queryOptions({
    queryKey: messagingKeys.pageThread(pageId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/pages/{page_id}/thread', { params: { path: { page_id: pageId } } }),
      ),
    staleTime: 5 * 60_000,
  })

export function useChannels() {
  return usePaged({ ...channelsQuery, refetchOnWindowFocus: true })
}

export function useDms() {
  return usePaged(dmsQuery)
}

/** Unread counters by conversation id (absent: nothing unread). */
export function useUnread(): Map<string, Unread> {
  const { data } = useQuery(unreadQuery)
  return useMemo(() => new Map((data?.items ?? []).map((u) => [u.conversation_id, u])), [data])
}

export function useConversation(conversationId: string) {
  return useQuery(conversationQuery(conversationId))
}

export function usePageThread(pageId: string) {
  return useQuery(pageThreadQuery(pageId))
}

/** After a conversation turned out to be gone: the sidebar lists and counters forget it. */
export function useForgetGone() {
  const queryClient = useQueryClient()
  return useCallback(() => {
    for (const queryKey of [messagingKeys.channels, messagingKeys.dms, messagingKeys.unread]) {
      void queryClient.invalidateQueries({ queryKey: [...queryKey] })
    }
  }, [queryClient])
}

function storeConversation(queryClient: QueryClient, conversation: Conversation) {
  queryClient.setQueryData(messagingKeys.conversation(conversation.id), conversation)
}

export function useCreateChannel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ spaceId, ...body }: Schemas['ChannelCreate'] & { spaceId: string }) =>
      unwrap(
        await api.POST('/api/spaces/{space_id}/channels', {
          params: { path: { space_id: spaceId } },
          body,
        }),
      ),
    onSuccess: (channel) => {
      storeConversation(queryClient, channel)
      void queryClient.invalidateQueries({ queryKey: messagingKeys.channels })
    },
  })
}

/** Opens the direct message with these people (the existing one, if there is one). */
export function useOpenDm() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (userIds: string[]) =>
      unwrap(await api.POST('/api/dms', { body: { user_ids: userIds } })),
    onSuccess: (dm) => {
      storeConversation(queryClient, dm)
      void queryClient.invalidateQueries({ queryKey: messagingKeys.dms })
    },
  })
}

/** Moves the read position forward (the server ignores a step back). */
export function useMarkRead(conversationId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (messageId: string) =>
      unwrap(
        await api.POST('/api/conversations/{conversation_id}/read', {
          params: { path: { conversation_id: conversationId } },
          body: { message_id: messageId },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: messagingKeys.unread }),
  })
}
