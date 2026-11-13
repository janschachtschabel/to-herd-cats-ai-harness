import { CATEGORIES, KINDS, PRIORITIES, UNFINISHED, type Priority } from './display'
import type { StatusCategory, TicketKind } from './display'

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
export const SORTS = ['updated', 'due', 'priority', 'number'] as const
export type TicketSort = (typeof SORTS)[number]

/** The list's filters as they stand in the address (`/tickets?…`). Left out, the list
 *  is "my tickets": assigned to me, not finished. `who=all` drops the assignee,
 *  `state=all` the status, `state=<category>` keeps one category. */
export interface TicketSearch {
  who?: 'all'
  state?: 'all' | StatusCategory
  space?: string
  kind?: TicketKind
  priority?: Priority
  tag?: string
  q?: string
  sort?: TicketSort
}

const pick = <T extends string>(values: readonly T[], value: unknown): T | undefined =>
  values.includes(value as T) ? (value as T) : undefined

const id = (value: unknown) =>
  typeof value === 'string' && ID.test(value) ? value.toLowerCase() : undefined

/** The address's filters, each only if valid (the router's `validateSearch`). Every
 *  key is present (undefined if invalid): the router lays the result over the raw
 *  address, so a left-out key would keep an invalid value. */
export function ticketSearch(search: Record<string, unknown>): TicketSearch {
  const q = typeof search.q === 'string' ? search.q.trim().slice(0, 200) : ''
  const out: TicketSearch = {
    who: search.who === 'all' ? 'all' : undefined,
    state: search.state === 'all' ? 'all' : pick(CATEGORIES, search.state),
    space: id(search.space),
    kind: pick(KINDS, search.kind),
    priority: pick(PRIORITIES, search.priority),
    tag: id(search.tag),
    q: q || undefined,
    sort: pick(SORTS, search.sort),
  }
  return out
}

/** The query of `GET /api/tickets` for these filters. */
export function listQuery(search: TicketSearch) {
  const state = search.state
  return {
    assignee: search.who === 'all' ? undefined : 'me',
    status_category: state === 'all' ? undefined : state ? [state] : [...UNFINISHED],
    space_id: search.space,
    kind: search.kind,
    priority: search.priority,
    tag: search.tag ? [search.tag] : undefined,
    q: search.q,
    sort: search.sort ?? 'updated',
  }
}

/** Whether the list shows the default "my tickets" (nothing chosen). */
export function isMine(search: TicketSearch): boolean {
  return search.who !== 'all'
}
