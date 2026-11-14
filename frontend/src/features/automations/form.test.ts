import { describe, expect, test } from 'vitest'
import { makeAutomation } from '@/test/automations'
import { checkValues, createBody, newValues, scheduleOf, updateBody, valuesOf } from './form'

const AGENT = { id: '00000000-0000-7000-8000-0000000000a1', name: 'Hilda' }

describe('the automation form', () => {
  test('a new one is a daily term in my DM in my zone', () => {
    const values = newValues({ zone: 'Europe/Berlin', agent: AGENT })
    values.instruction = 'Fasse den Tag zusammen.'
    expect(createBody(values)).toEqual({
      agent_id: AGENT.id,
      place: { type: 'dm' },
      instruction: 'Fasse den Tag zusammen.',
      schedule: { kind: 'recurring', cron: '0 9 * * *', time_zone: 'Europe/Berlin' },
    })
    expect(checkValues(values, 'create')).toEqual({})
  })

  test('each kind becomes its schedule', () => {
    const base = newValues({ zone: 'Europe/Berlin', agent: AGENT })
    expect(
      scheduleOf({ ...base, kind: 'once', onceDate: '2026-11-20', onceTime: '14:30' }),
    ).toEqual({ kind: 'once', at: '2026-11-20T13:30:00.000Z' })
    expect(
      scheduleOf({
        ...base,
        kind: 'heartbeat',
        interval: '30',
        days: [5, 1],
        from: '22:00',
        until: '06:00',
      }),
    ).toEqual({
      kind: 'heartbeat',
      interval_minutes: 30,
      active_days: [1, 5],
      active_from: '22:00:00',
      active_until: '06:00:00',
      time_zone: 'Europe/Berlin',
    })
    expect(
      scheduleOf({
        ...base,
        kind: 'event',
        eventType: 'ticket.created',
        tagId: 't-1',
        ticketKind: 'bug',
        quietMinutes: '10',
      }),
    ).toEqual({
      kind: 'event',
      event_type: 'ticket.created',
      quiet_seconds: 600,
      filter_tag_id: 't-1',
      filter_ticket_kind: 'bug',
    })
    // Filters only for `ticket.created`.
    expect(
      scheduleOf({
        ...base,
        kind: 'event',
        eventType: 'page.published',
        tagId: 't-1',
        ticketKind: 'bug',
      }),
    ).toEqual({
      kind: 'event',
      event_type: 'page.published',
      quiet_seconds: 300,
      filter_tag_id: null,
      filter_ticket_kind: null,
    })
  })

  test('the places: a channel by id, a ticket by its number', () => {
    const base = { ...newValues({ zone: 'UTC', agent: AGENT }), instruction: 'x' }
    expect(createBody({ ...base, placeType: 'channel', conversationId: 'c-1' }).place).toEqual({
      type: 'channel',
      conversation_id: 'c-1',
    })
    expect(createBody({ ...base, placeType: 'ticket', ticketNumber: 'HC-42' }).place).toEqual({
      type: 'ticket',
      ticket_number: 42,
    })
  })

  test('what is missing or out of bounds is named at its field', () => {
    const values = {
      ...newValues({ zone: 'Europe/Berlin', agent: null }),
      placeType: 'ticket' as const,
      ticketNumber: 'abc',
    }
    expect(checkValues(values, 'create')).toEqual({
      agent: 'Bitte einen Agenten wählen.',
      place: 'Bitte eine Ticketnummer angeben, etwa HC-12.',
      instruction: 'Bitte ausfüllen.',
    })
    const heartbeat = {
      ...newValues({ zone: 'Europe/Berlin', agent: AGENT }),
      instruction: 'x'.repeat(4001),
      kind: 'heartbeat' as const,
      interval: '5',
      days: [],
      zone: '',
    }
    expect(checkValues(heartbeat, 'create')).toEqual({
      instruction: 'Höchstens 4000 Zeichen.',
      interval: 'Zwischen 15 und 1440 Minuten.',
      days: 'Mindestens einen Wochentag wählen.',
      zone: 'Bitte ausfüllen.',
    })
    const event = {
      ...newValues({ zone: 'UTC', agent: AGENT }),
      instruction: 'x',
      kind: 'event' as const,
      placeType: 'channel' as const,
      conversationId: 'c-1',
      quietMinutes: '0',
    }
    expect(checkValues(event, 'create')).toEqual({ quiet: 'Zwischen 1 und 1440 Minuten.' })
    const once = {
      ...newValues({ zone: 'UTC', agent: AGENT }),
      instruction: 'x',
      kind: 'once' as const,
    }
    expect(checkValues(once, 'create')).toEqual({ once: 'Bitte Datum und Uhrzeit angeben.' })
    const custom = { ...newValues({ zone: 'UTC', agent: AGENT }), instruction: 'x' }
    custom.preset = { ...custom.preset, kind: 'custom', cron: '' }
    expect(checkValues(custom, 'create')).toEqual({ cron: 'Bitte ausfüllen.' })
  })

  test('a stored automation reads back into the form and saves only what changed', () => {
    const stored = makeAutomation({
      kind: 'recurring',
      cron: '30 8 * * 1-5',
      time_zone: 'Europe/Berlin',
      instruction: 'Alt',
      version: 4,
    })
    const values = valuesOf(stored, 'Europe/Berlin')
    expect(values.preset).toMatchObject({ kind: 'weekdays', time: '08:30' })
    expect(updateBody({ ...values, instruction: 'Neu' }, stored)).toEqual({
      version: 4,
      instruction: 'Neu',
    })
    const later = { ...values, preset: { ...values.preset, time: '09:00' } }
    expect(updateBody(later, stored)).toEqual({
      version: 4,
      instruction: 'Alt',
      schedule: { kind: 'recurring', cron: '0 9 * * 1-5', time_zone: 'Europe/Berlin' },
    })
  })

  test('a heartbeat and a once read back', () => {
    const beat = makeAutomation({
      kind: 'heartbeat',
      cron: null,
      interval_minutes: 60,
      active_days: [1, 2, 3],
      active_from: '09:00:00',
      active_until: '17:00:00',
      time_zone: 'UTC',
    })
    expect(valuesOf(beat, 'UTC')).toMatchObject({
      kind: 'heartbeat',
      interval: '60',
      days: [1, 2, 3],
      from: '09:00',
      until: '17:00',
      zone: 'UTC',
    })
    const once = makeAutomation({
      kind: 'once',
      cron: null,
      time_zone: null,
      next_due_at: '2026-11-20T13:30:00Z',
    })
    expect(valuesOf(once, 'Europe/Berlin')).toMatchObject({
      kind: 'once',
      onceDate: '2026-11-20',
      onceTime: '14:30',
      zone: 'Europe/Berlin',
    })
  })
})
