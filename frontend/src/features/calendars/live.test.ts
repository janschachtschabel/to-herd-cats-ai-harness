import { QueryClient } from '@tanstack/react-query'
import { describe, expect, test } from 'vitest'
import { invalidateFor } from '@/features/messaging/live'
import { ticketKeys } from '@/features/tickets/keys'
import type { LiveEvent } from '@/lib/live'
import { calendarKeys } from './keys'

const KEYS = {
  calendars: calendarKeys.calendars,
  spaceCalendars: calendarKeys.space('space'),
  otherSpaceCalendars: calendarKeys.space('other'),
  window: calendarKeys.window({ from: 'a', to: 'b', timeZone: 'UTC' }),
  namedWindow: calendarKeys.window({ from: 'a', to: 'b', timeZone: 'UTC', spaceId: 'other' }),
  event: calendarKeys.event('e'),
  tickets: ticketKeys.counts,
  spaces: ['spaces', 'sidebar'],
}

function after(event: Partial<LiveEvent>) {
  const client = new QueryClient()
  const held = { items: [{ id: 'kept' }] }
  for (const key of Object.values(KEYS)) client.setQueryData(key, held)
  invalidateFor(client, {
    type: 'calendar.changed',
    conversationId: null,
    messageId: null,
    parentId: null,
    ticketId: null,
    spaceId: null,
    ...event,
  })
  const stale = Object.entries(KEYS)
    .filter(([, key]) => client.getQueryState(key)?.isInvalidated)
    .map(([name]) => name)
  // Nothing is taken from the event: every query holds what it held.
  const untouched = Object.values(KEYS).every((key) => client.getQueryData(key) === held)
  return { stale, untouched }
}

describe('calendar.changed', () => {
  test('marks only the calendar queries its space can change stale, writing nothing', () => {
    expect(after({ spaceId: 'space', calendarId: 'cal' })).toEqual({
      stale: ['calendars', 'spaceCalendars', 'window', 'namedWindow', 'event'],
      untouched: true,
    })
  })

  test('without a space, every calendar query', () => {
    expect(after({}).stale).toEqual([
      'calendars',
      'spaceCalendars',
      'otherSpaceCalendars',
      'window',
      'namedWindow',
      'event',
    ])
  })
})
