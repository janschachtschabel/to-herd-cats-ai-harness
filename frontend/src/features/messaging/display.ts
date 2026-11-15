import type { TFunction } from 'i18next'
import { ticketSystemText } from '@/features/tickets/display'
import { ticketKey } from '@/features/tickets/refs'
import type { SystemEntry } from '@/lib/api'

interface Named {
  kind: 'channel' | 'dm' | 'thread_page' | 'thread_ticket'
  name: string | null
  participants?: { id: string; name: string; is_active: boolean }[]
  /** A ticket thread's ticket (activity entries and search hits carry it). */
  ticket_number?: number | null
}

/** The other people of a direct message, by name ("Jan, Lea"); just "direct message"
 *  where the people are not given. */
export function dmLabel(t: TFunction, conversation: Named, meId: string | undefined): string {
  if (!conversation.participants) return t('messaging.dm.short')
  const others = (conversation.participants ?? []).filter((p) => p.id !== meId)
  if (others.length === 0) return t('messaging.dm.onlyMe')
  return others
    .map((p) => (p.is_active ? p.name : t('messaging.dm.inactive', { name: p.name })))
    .join(', ')
}

/** What a conversation is called in lists and headers. */
export function conversationLabel(
  t: TFunction,
  conversation: Named,
  meId: string | undefined,
): string {
  if (conversation.kind === 'channel') return `# ${conversation.name ?? ''}`
  if (conversation.kind === 'dm') return dmLabel(t, conversation, meId)
  if (conversation.kind === 'thread_ticket' && conversation.ticket_number) {
    return ticketKey(conversation.ticket_number)
  }
  return t('messaging.discussion.title')
}

const SYSTEM_KEYS = [
  'page.created',
  'page.published',
  'page.moved',
  'page.trashed',
  'page.restored',
  'page.version_restored',
  'proposal.created',
  'proposal.accepted',
  'proposal.rejected',
  'proposal.withdrawn',
  'page.review_due',
  'automation.started',
] as const

/** A timeline entry (page or ticket thread, or a channel's thread root that an
 *  automation opened) in words, from its key and parameters. */
export function systemText(t: TFunction, entry: SystemEntry, locale = 'de'): string {
  if (entry.key.startsWith('ticket.')) return ticketSystemText(t, entry, locale)
  const actor = entry.actor?.name ?? t('messaging.system.someone')
  const key = (SYSTEM_KEYS as readonly string[]).includes(entry.key) ? entry.key : 'unknown'
  return t(`messaging.system.${key.replace('.', '_')}`, { actor, number: entry.number ?? '' })
}
