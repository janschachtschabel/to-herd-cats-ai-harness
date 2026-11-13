import { useNavigate } from '@tanstack/react-router'
import { useCallback } from 'react'

interface Where {
  id: string
  kind: 'channel' | 'dm' | 'thread_page' | 'thread_ticket'
  page_id: string | null
}

/** Where a message is shown: a channel or direct message on its own screen, a page
 *  thread's message in the page's discussion. `thread`: the thread it is a reply in. */
export type MessageTarget =
  | { to: 'conversation'; conversationId: string; thread?: string; message: string }
  | { to: 'page'; pageId: string; thread?: string; message: string }

export function messageTarget(
  conversation: Where,
  messageId: string,
  parentId: string | null,
): MessageTarget {
  const thread = parentId ?? undefined
  if (conversation.kind === 'thread_page' && conversation.page_id) {
    return { to: 'page', pageId: conversation.page_id, thread, message: messageId }
  }
  return { to: 'conversation', conversationId: conversation.id, thread, message: messageId }
}

/** Opens a message where it is shown. */
export function useOpenMessage() {
  const navigate = useNavigate()
  return useCallback(
    (target: MessageTarget) => {
      const search = { thread: target.thread, message: target.message }
      if (target.to === 'page') {
        void navigate({ to: '/go/page/$pageId', params: { pageId: target.pageId }, search })
      } else {
        void navigate({
          to: '/c/$conversationId',
          params: { conversationId: target.conversationId },
          search,
        })
      }
    },
    [navigate],
  )
}
