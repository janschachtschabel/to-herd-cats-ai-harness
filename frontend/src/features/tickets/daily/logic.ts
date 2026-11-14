import type { Sprint, TicketSummary } from '@/lib/api'
import type { BoardFilters } from '../board/queries'
import { activeSprint } from '../sprints/rules'

/** The sprint the board shows: the one chosen (`all`: none chosen on purpose), else in
 *  the daily view the running sprint (plan M4b, decision 5), else all tickets. */
export function boardSprint(
  filters: BoardFilters,
  grouped: boolean,
  sprints: Sprint[] | undefined,
): string | undefined {
  if (filters.sprint !== undefined) return filters.sprint
  return grouped ? activeSprint(sprints ?? [])?.id : undefined
}

/** A card loaded after a cell's first page is marked by the same rule as the server's:
 *  its status changed (or it was made) at or after the board's `changed_since`. */
export function changedSince(ticket: Pick<TicketSummary, 'status_changed_at'>, since: string) {
  return Date.parse(ticket.status_changed_at) >= Date.parse(since)
}

/** The start of the last working day in words ("Freitag, 13.11."): a day in UTC, as
 *  the server reckons it. */
export function formatWorkingDay(since: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    weekday: 'long',
    day: 'numeric',
    month: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(since))
}

/** A person filter that names one row (a person's id or `none`), not `me`. */
export function focusedPerson(filters: BoardFilters): string | undefined {
  return filters.assignee && filters.assignee !== 'me' ? filters.assignee : undefined
}

/** The filters once the daily view is left: a person picked there is let go (the
 *  board's own person filter is "only mine"). */
export function withoutFocus(filters: BoardFilters): BoardFilters {
  return focusedPerson(filters) ? { ...filters, assignee: undefined } : filters
}
