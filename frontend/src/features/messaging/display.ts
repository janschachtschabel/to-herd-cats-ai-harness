import type { TFunction } from 'i18next'
import type { SystemEntry } from '@/lib/api'

interface Named {
  kind: 'channel' | 'dm' | 'thread_page'
  name: string | null
  participants?: { id: string; name: string; is_active: boolean }[]
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
  return t('messaging.discussion.title')
}

const SYSTEM_KEYS = [
  'page.created',
  'page.published',
  'page.moved',
  'page.trashed',
  'page.restored',
  'page.version_restored',
] as const

/** A page thread's timeline entry in words, from its key and parameters. */
export function systemText(t: TFunction, entry: SystemEntry): string {
  const actor = entry.actor?.name ?? t('messaging.system.someone')
  const key = (SYSTEM_KEYS as readonly string[]).includes(entry.key) ? entry.key : 'unknown'
  return t(`messaging.system.${key.replace('.', '_')}`, { actor, number: entry.number ?? '' })
}
