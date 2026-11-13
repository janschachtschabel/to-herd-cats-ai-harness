import type { TFunction } from 'i18next'
import type { Schemas, SystemEntry } from '@/lib/api'
import { formatDay } from '@/lib/format'

export type TicketKind = Schemas['TicketKind']
export type Priority = Schemas['Priority']
export type StatusCategory = Schemas['StatusCategory']

export const KINDS: readonly TicketKind[] = ['epic', 'story', 'task', 'bug']
export const PRIORITIES: readonly Priority[] = ['urgent', 'high', 'normal', 'low']
export const CATEGORIES: readonly StatusCategory[] = [
  'open',
  'active',
  'review',
  'done',
  'cancelled',
]
/** "Not finished": what "my tickets" shows (plan M4, Task 5). */
export const UNFINISHED: readonly StatusCategory[] = ['open', 'active', 'review']

/** Decorative colour of a category (the text beside it carries the meaning). */
export const CATEGORY_DOT: Record<StatusCategory, string> = {
  open: 'bg-slate-400',
  active: 'bg-blue-500',
  review: 'bg-amber-500',
  done: 'bg-emerald-500',
  cancelled: 'bg-zinc-300 dark:bg-zinc-600',
}

/** The kinds a ticket of `kind` may have as parent (plan M4, decision 5). */
export function parentKinds(kind: TicketKind): TicketKind[] {
  if (kind === 'epic') return []
  if (kind === 'story') return ['epic']
  return ['epic', 'story']
}

type Value = SystemEntry['old']

const TICKET_KEYS = [
  'ticket.created',
  'ticket.status_changed',
  'ticket.assigned',
  'ticket.unassigned',
  'ticket.priority_changed',
  'ticket.kind_changed',
  'ticket.parent_changed',
  'ticket.due_changed',
  'ticket.title_changed',
  'ticket.description_changed',
  'ticket.page_linked',
  'ticket.page_unlinked',
] as const

/** A ticket thread's timeline entry in words, from its key and its old and new values
 *  (ids come named by the server; enumeration values and days are worded here). */
export function ticketSystemText(t: TFunction, entry: SystemEntry, locale: string): string {
  const actor = entry.actor?.name ?? t('messaging.system.someone')
  const key = (TICKET_KEYS as readonly string[]).includes(entry.key) ? entry.key : 'unknown'
  const name = (value: Value, fallback: string) => value?.name ?? fallback
  const someone = t('messaging.system.someone')
  const params: Record<string, string> = { actor }
  let variant = key.replace('ticket.', '')
  switch (key) {
    case 'ticket.status_changed':
      params.from = name(entry.old, t('tickets.timeline.goneStatus'))
      params.to = name(entry.new, t('tickets.timeline.goneStatus'))
      break
    case 'ticket.assigned':
      params.to = name(entry.new, someone)
      break
    case 'ticket.unassigned':
      params.from = name(entry.old, someone)
      break
    case 'ticket.priority_changed':
      params.from = entry.old ? t(`tickets.priorities.${entry.old.value as Priority}`) : ''
      params.to = entry.new ? t(`tickets.priorities.${entry.new.value as Priority}`) : ''
      break
    case 'ticket.kind_changed':
      params.from = entry.old ? t(`tickets.kinds.${entry.old.value as TicketKind}`) : ''
      params.to = entry.new ? t(`tickets.kinds.${entry.new.value as TicketKind}`) : ''
      break
    case 'ticket.parent_changed':
      variant = entry.new ? 'parent_set' : 'parent_removed'
      params.to = name(entry.new, '')
      params.from = name(entry.old, '')
      break
    case 'ticket.due_changed':
      variant = entry.new ? 'due_set' : 'due_removed'
      params.to = entry.new ? formatDay(entry.new.value, locale) : ''
      break
    case 'ticket.page_linked':
      variant = entry.new?.name ? 'page_linked' : 'page_linked_hidden'
      params.title = entry.new?.name ?? ''
      break
    case 'ticket.page_unlinked':
      variant = entry.old?.name ? 'page_unlinked' : 'page_unlinked_hidden'
      params.title = entry.old?.name ?? ''
      break
  }
  return t(`tickets.timeline.${variant}`, params)
}

/** How many children a ticket has, over every category. */
export function childTotal(counts: Schemas['ChildCounts']): number {
  return CATEGORIES.reduce((sum, category) => sum + counts[category], 0)
}
