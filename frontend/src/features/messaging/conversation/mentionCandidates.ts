import { useMemo } from 'react'
import { useDirectory } from '@/features/directory/queries'
import type { Conversation, DirectoryEntry } from '@/lib/api'

const NOBODY = new Set<string>()
const SHOWN = 8

export interface MentionCandidates {
  items: DirectoryEntry[]
  isPending: boolean
  isError: boolean
  error: unknown
}

/** Whom `@query` may name in a conversation: in a direct message its other active
 *  participants; elsewhere the people who may read the conversation's space (the
 *  server tells no one else, so no one else is offered). */
export function useMentionCandidates(
  conversation: Conversation,
  query: string,
  enabled: boolean,
  meId: string | undefined,
): MentionCandidates {
  const dm = conversation.kind === 'dm'
  const spaceId = conversation.space_id ?? undefined
  const people = useDirectory(
    query,
    NOBODY,
    enabled && !dm && spaceId !== undefined,
    'user',
    spaceId,
  )
  const participants = useMemo(() => {
    const q = query.toLowerCase()
    return (conversation.participants ?? [])
      .filter((p) => p.is_active && p.id !== meId && p.name.toLowerCase().includes(q))
      .map((p): DirectoryEntry => ({ type: 'user', id: p.id, name: p.name }))
  }, [conversation.participants, query, meId])
  if (dm)
    return { items: participants.slice(0, SHOWN), isPending: false, isError: false, error: null }
  return {
    items: enabled ? people.items.slice(0, SHOWN) : [],
    isPending: people.isPending,
    isError: people.isError,
    error: people.error,
  }
}
