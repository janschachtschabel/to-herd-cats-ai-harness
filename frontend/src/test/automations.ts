import type { Schemas } from '@/lib/api'

type Automation = Schemas['AutomationOut']
type Firing = Schemas['FiringOut']

let counter = 0
const id = () => `00000000-0000-7000-8000-7${String(++counter).padStart(11, '0')}`

export const HILDA_AGENT = { id: '00000000-0000-7000-8000-0000000000a1', name: 'Hilda' }
export const MIA = { id: '00000000-0000-7000-8000-0000000000b1', name: 'Mia Muster' }

export const ALL_ABILITIES: Automation['abilities'] = {
  edit: true,
  pause: true,
  resume: false,
  delete: true,
  run: true,
  take_over: false,
}

/** A daily automation of Mia's with Hilda in her DM, every ability its owner has. */
export function makeAutomation(overrides: Partial<Automation> = {}): Automation {
  return {
    id: id(),
    kind: 'recurring',
    state: 'active',
    paused_reason: null,
    version: 1,
    instruction: 'Fasse zusammen, was gestern im Kanal besprochen wurde.',
    agent: HILDA_AGENT,
    owner: MIA,
    place: {
      type: 'dm',
      conversation_id: 'dm-1',
      space_id: null,
      name: null,
      ticket_number: null,
    },
    next_due_at: '2026-11-16T08:00:00Z',
    cron: '0 9 * * *',
    time_zone: 'Europe/Berlin',
    interval_minutes: null,
    active_days: null,
    active_from: null,
    active_until: null,
    event_type: null,
    quiet_seconds: null,
    filter_tag_id: null,
    filter_ticket_kind: null,
    last_run: null,
    upcoming: ['2026-11-16T08:00:00Z', '2026-11-17T08:00:00Z'],
    abilities: ALL_ABILITIES,
    ...overrides,
  }
}

export function makeFiring(overrides: Partial<Firing> = {}): Firing {
  return {
    id: id(),
    due_at: '2026-11-15T08:00:00Z',
    fired_at: '2026-11-15T08:00:01Z',
    outcome: 'started',
    run_id: id(),
    heartbeat_ok: false,
    ...overrides,
  }
}
