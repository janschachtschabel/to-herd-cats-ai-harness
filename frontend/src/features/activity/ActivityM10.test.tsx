import { screen, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { makeMe, mockApi, page } from '@/test/api'
import { makeActivity, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import type { ActivityCalendarEvent } from '@/lib/api'

function calendarEntry(
  reason: 'invitation' | 'invite_reply',
  event: Partial<ActivityCalendarEvent> = {},
) {
  return makeActivity({
    reason,
    conversation: null,
    message_id: null,
    author: null,
    snippet: '',
    calendar_event: {
      id: `ev-${reason}-${event.title ?? 'Planung'}`,
      title: 'Planung',
      starts_at: '2026-11-23T09:00:00Z',
      ends_at: '2026-11-23T10:00:00Z',
      all_day: false,
      cancelled: false,
      response: 'needs_action',
      ...event,
    },
  })
}

describe('activity entries of M10 (invitations)', () => {
  test('an invitation names the event, its start and one’s own answer, and no author', async () => {
    mockApi({
      ...shellRoutes(makeMe([])),
      'GET /api/activity': page([
        calendarEntry('invitation'),
        calendarEntry('invitation', { title: 'Sommerfest', cancelled: true }),
        calendarEntry('invitation', {
          title: 'Klausur',
          all_day: true,
          starts_at: '2026-11-25T00:00:00Z',
          response: 'tentative',
        }),
        calendarEntry('invite_reply', { title: 'Retro', response: null }),
      ]),
    })
    await renderApp('/activity')
    const invited = (await screen.findByText('Du bist zu „Planung“ eingeladen.')).closest('li')!
    expect(invited).toHaveTextContent('Deine Antwort: noch offen')
    expect(invited).not.toHaveTextContent('Unbekannt')
    expect(within(invited).queryByRole('button', { name: 'Öffnen' })).toBeNull()
    const cancelled = screen.getByText('„Sommerfest“ wurde abgesagt.').closest('li')!
    expect(cancelled).not.toHaveTextContent('Deine Antwort')
    const allDay = screen.getByText('Du bist zu „Klausur“ eingeladen.').closest('li')!
    expect(allDay).toHaveTextContent('25.11.2026')
    expect(allDay).toHaveTextContent('Deine Antwort: vielleicht')
    const replied = screen
      .getByText('Für „Retro“ hat jemand abgesagt oder „vielleicht“ geantwortet.')
      .closest('li')!
    expect(replied).not.toHaveTextContent('Deine Antwort')
  })
})
