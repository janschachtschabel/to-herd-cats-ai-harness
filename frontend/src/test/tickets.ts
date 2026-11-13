import type { Ticket, TicketStatus, TicketSummary } from '@/lib/api'
import { uid } from './messaging'

export const STATUSES: TicketStatus[] = [
  ['Neu', 'open'],
  ['In Arbeit', 'active'],
  ['Zur Prüfung', 'review'],
  ['Erledigt', 'done'],
  ['Verworfen', 'cancelled'],
].map(([name, category], position) => ({
  id: `00000000-0000-7000-a000-00000000000${position + 1}`,
  space_id: 'space-1',
  name: name!,
  position,
  category: category as TicketStatus['category'],
  version: 1,
}))

export const statusRef = (status: TicketStatus) => ({
  id: status.id,
  name: status.name,
  category: status.category,
})

export function makeTicketSummary(overrides: Partial<TicketSummary> = {}): TicketSummary {
  const number = overrides.number ?? 42
  return {
    id: uid(),
    number,
    key: `HC-${number}`,
    space_id: 'space-1',
    kind: 'task',
    title: 'Login schlägt fehl',
    status: statusRef(STATUSES[0]!),
    priority: 'normal',
    assignee: null,
    reporter: { type: 'user', id: 'jan', name: 'Jan Jansen' },
    due_on: null,
    parent: null,
    sprint_id: null,
    tags: [],
    version: 1,
    created_at: '2026-11-13T08:00:00Z',
    updated_at: '2026-11-13T08:00:00Z',
    status_changed_at: '2026-11-13T08:00:00Z',
    ...overrides,
  }
}

export function makeTicket(overrides: Partial<Ticket> = {}): Ticket {
  return {
    ...makeTicketSummary(overrides),
    description_md: 'Beim **Anmelden** passiert nichts.',
    children: { open: 0, active: 0, review: 0, done: 0, cancelled: 0 },
    ...overrides,
  }
}
