import { KINDS } from '../display'
import type { BoardFilters } from './queries'

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** The board as it stands in the address (`/spaces/<id>/board?…`), so a reload or a
 *  shared link keeps it (module review M4b, finding 9): the filters and, with
 *  `group=assignee`, the daily view. */
export interface BoardSearch extends BoardFilters {
  group?: 'assignee'
}

const id = (value: unknown) =>
  typeof value === 'string' && ID.test(value) ? value.toLowerCase() : undefined

const idOr = <T extends string>(words: readonly T[], value: unknown): string | undefined =>
  words.includes(value as T) ? (value as T) : id(value)

/** The address's board, each key only if valid (the router's `validateSearch`); every
 *  key is present (undefined if invalid), so an invalid value is not kept. */
export function boardSearch(search: Record<string, unknown>): BoardSearch {
  return {
    group: search.group === 'assignee' ? 'assignee' : undefined,
    assignee: idOr(['me', 'none'], search.assignee),
    kind: KINDS.includes(search.kind as never) ? (search.kind as BoardFilters['kind']) : undefined,
    tag: id(search.tag),
    epic: id(search.epic),
    sprint: idOr(['none', 'all'], search.sprint),
  }
}
