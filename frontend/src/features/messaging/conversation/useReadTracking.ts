import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { readPositionQuery, unreadQuery, useMarkRead } from '../queries'
import type { useMessages } from './queries'
import { firstAfterPosition, firstUnreadId } from './timeline'

/**
 * Where the "new" marker goes and keeping the read position up to date. The marker is
 * placed once, from the read position fetched when the conversation opened (it stays
 * while one reads); before anything was read there (or if the position cannot be had)
 * from the unread count, which knows which conversations count unread at all. Then the
 * newest message is marked read whenever the tab is visible.
 */
export function useReadTracking(
  conversationId: string,
  list: ReturnType<typeof useMessages>,
  meId: string | undefined,
): string | null {
  const unread = useQuery(unreadQuery)
  const position = useQuery(readPositionQuery(conversationId))
  const [marker, setMarker] = useState<string | null | undefined>(undefined)
  const markRead = useMarkRead(conversationId)
  const { mutate } = markRead
  const marked = useRef<string | null>(null)
  const newest = list.messages[0]?.id

  // Placed once, while rendering (React's way to derive state from what arrived).
  if (marker === undefined && list.loaded && unread.isFetched && position.isFetchedAfterMount) {
    const id = position.data?.last_read_message_id
    const at = position.data?.last_read_message_at
    if (id && at) {
      setMarker(firstAfterPosition(list.messages, { id, at }, meId))
    } else {
      const count =
        unread.data?.items.find((u) => u.conversation_id === conversationId)?.unread ?? 0
      setMarker(firstUnreadId(list.messages, count, meId))
    }
  }

  useEffect(() => {
    if (marker === undefined || !newest) return
    const mark = () => {
      if (document.visibilityState !== 'visible' || marked.current === newest) return
      marked.current = newest
      mutate(newest)
    }
    mark()
    document.addEventListener('visibilitychange', mark)
    return () => document.removeEventListener('visibilitychange', mark)
  }, [marker, newest, mutate])

  return marker ?? null
}
