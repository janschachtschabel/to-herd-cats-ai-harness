import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import { apiError, makeEntry, makeMe, makeSpace, makeTag, mockApi, page } from '@/test/api'
import { HILDA_AGENT, makeAutomation } from '@/test/automations'
import { makeConversation, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'

vi.mock('@/features/automations/zoned', async (original) => ({
  ...(await original<typeof import('./zoned')>()),
  viewerZone: () => 'Europe/Berlin',
}))

const me = makeMe(['directory.read', 'ai.use'])
const hilda = makeEntry({ type: 'agent', id: HILDA_AGENT.id, name: HILDA_AGENT.name })
const TERMS = [
  '2026-11-16T07:30:00Z',
  '2026-11-17T07:30:00Z',
  '2026-11-18T07:30:00Z',
  '2026-11-19T07:30:00Z',
  '2026-11-20T07:30:00Z',
]

function formApi(extra: Record<string, unknown> = {}) {
  const created = makeAutomation({ id: 'au-new' })
  return mockApi({
    ...shellRoutes(me),
    'GET /api/automations': page([]),
    'GET /api/directory': (call: { query: URLSearchParams }) =>
      page(call.query.get('type') === 'agent' ? [hilda] : []),
    'POST /api/automations/preview': { terms: TERMS },
    'POST /api/automations': { status: 201, body: created },
    'GET /api/automations/au-new': created,
    'GET /api/automations/au-new/firings': page([]),
    ...(extra as Record<string, object>),
  })
}

async function openForm(path = '/automations') {
  const rendered = await renderApp(path)
  await rendered.user.click(await screen.findByRole('button', { name: 'Neue Aufgabe' }))
  const dialog = await screen.findByRole('dialog', { name: 'Neue Aufgabe' })
  return { ...rendered, dialog }
}

async function pickHilda(user: Awaited<ReturnType<typeof renderApp>>['user'], dialog: HTMLElement) {
  await user.click(within(dialog).getByRole('combobox', { name: 'Agent' }))
  await user.click(await within(dialog).findByRole('option', { name: /Hilda/ }))
}

describe('making an automation', () => {
  test('a weekday preset writes its cron, previews five terms and is saved', async () => {
    const api = formApi()
    const { user, dialog, router } = await openForm()
    await pickHilda(user, dialog)
    await user.type(within(dialog).getByRole('textbox', { name: 'Auftrag' }), 'Fasse zusammen.')
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Zeitplan' }), 'weekdays')
    const time = within(dialog).getByLabelText('Uhrzeit')
    await user.clear(time)
    await user.type(time, '08:30')
    await waitFor(() =>
      expect(api.find('POST', '/api/automations/preview').at(-1)?.body).toEqual({
        schedule: { kind: 'recurring', cron: '30 8 * * 1-5', time_zone: 'Europe/Berlin' },
      }),
    )
    const preview = await within(dialog).findByRole('list', { name: 'Die nächsten Termine' })
    expect(within(preview).getAllByRole('listitem')[0]).toHaveTextContent('16.11.2026, 08:30')
    expect(within(preview).getAllByRole('listitem')).toHaveLength(5)
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/automations/au-new'))
    expect(api.find('POST', '/api/automations')[0]?.body).toEqual({
      agent_id: HILDA_AGENT.id,
      place: { type: 'dm' },
      instruction: 'Fasse zusammen.',
      schedule: { kind: 'recurring', cron: '30 8 * * 1-5', time_zone: 'Europe/Berlin' },
    })
  })

  test("the expert field's cron is checked live, the API's reason in words", async () => {
    formApi({
      'POST /api/automations/preview': apiError(422, 'automation.too_frequent'),
    })
    const { user, dialog } = await openForm()
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Zeitplan' }), 'custom')
    const cron = within(dialog).getByRole('textbox', { name: 'Cron-Ausdruck' })
    await user.clear(cron)
    await user.type(cron, '*/5 * * * *')
    expect(
      await within(dialog).findByText(
        'Zu häufig: Zwischen zwei Terminen müssen mindestens 15 Minuten liegen.',
      ),
    ).toBeInTheDocument()
  })

  test('nothing is sent while something is missing; each field says what', async () => {
    const api = formApi()
    const { user, dialog } = await openForm()
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    expect(await within(dialog).findByText('Bitte einen Agenten wählen.')).toBeInTheDocument()
    expect(within(dialog).getByRole('textbox', { name: 'Auftrag' })).toHaveAccessibleDescription(
      /Bitte ausfüllen\./,
    )
    expect(api.find('POST', '/api/automations')).toEqual([])
  })

  test('once: a date and a time in a zone; a ticket as the place', async () => {
    const api = formApi()
    const { user, dialog } = await openForm()
    await pickHilda(user, dialog)
    await user.type(within(dialog).getByRole('textbox', { name: 'Auftrag' }), 'Erinnere mich.')
    await user.click(within(dialog).getByRole('radio', { name: /Einmalig/ }))
    await user.type(within(dialog).getByLabelText('Datum'), '2026-11-20')
    await user.click(within(dialog).getByRole('radio', { name: 'Ein Ticket' }))
    await user.type(within(dialog).getByRole('textbox', { name: 'Ticket' }), 'HC-12')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(api.find('POST', '/api/automations')).toHaveLength(1))
    expect(api.find('POST', '/api/automations')[0]?.body).toMatchObject({
      place: { type: 'ticket', ticket_number: 12 },
      schedule: { kind: 'once', at: '2026-11-20T08:00:00.000Z' },
    })
  })

  test('a heartbeat: interval, weekdays, hours, zone, and the HEARTBEAT_OK hint', async () => {
    const api = formApi()
    const { user, dialog } = await openForm()
    await pickHilda(user, dialog)
    await user.click(within(dialog).getByRole('radio', { name: /Heartbeat/ }))
    expect(within(dialog).getByText(/genau mit HEARTBEAT_OK, bleibt es still/)).toBeInTheDocument()
    await user.type(within(dialog).getByRole('textbox', { name: 'Checkliste' }), 'Offene Tickets?')
    const interval = within(dialog).getByRole('spinbutton', { name: 'Abstand in Minuten' })
    await user.clear(interval)
    await user.type(interval, '30')
    await user.click(within(dialog).getByRole('checkbox', { name: 'Freitag' }))
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(api.find('POST', '/api/automations')).toHaveLength(1))
    expect(api.find('POST', '/api/automations')[0]?.body).toMatchObject({
      instruction: 'Offene Tickets?',
      schedule: {
        kind: 'heartbeat',
        interval_minutes: 30,
        active_days: [1, 2, 3, 4],
        active_from: '09:00:00',
        active_until: '17:00:00',
        time_zone: 'Europe/Berlin',
      },
    })
  })

  test('an event rule only in a space I manage: hints, filters and quiet time', async () => {
    const space = makeSpace({ id: 's-1', name: 'Support', my_role: 'admin' })
    const channel = makeConversation({
      id: 'c-1',
      kind: 'channel',
      name: 'eingang',
      space_id: 's-1',
    })
    const bug = makeTag({ id: 't-bug', name: 'dringend', space_id: 's-1' })
    const api = formApi({
      'GET /api/spaces': page([space]),
      'GET /api/spaces/s-1': space,
      'GET /api/spaces/:id/pages/tree': page([]),
      'GET /api/spaces/s-1/automations': page([]),
      'GET /api/channels': page([channel]),
      'GET /api/tags': page([bug]),
    })
    const { user, dialog } = await openForm('/spaces/s-1/automations')
    await pickHilda(user, dialog)
    await user.type(within(dialog).getByRole('textbox', { name: 'Auftrag' }), 'Ordne ein.')
    await user.click(within(dialog).getByRole('radio', { name: /Ereignis-Regel/ }))
    expect(within(dialog).queryByRole('radio', { name: /Direktnachricht/ })).toBeNull()
    expect(
      within(dialog).getByText(/handelt mit deinen Rechten am Ort der Regel/),
    ).toBeInTheDocument()
    expect(
      within(dialog).getByText(/nur, was ein Betrachter des Bereichs sieht/),
    ).toBeInTheDocument()
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Kanal' }), 'c-1')
    await user.selectOptions(
      within(dialog).getByRole('combobox', { name: 'Nur Tickets mit Schlagwort' }),
      't-bug',
    )
    await user.selectOptions(
      within(dialog).getByRole('combobox', { name: 'Nur Tickets der Art' }),
      'bug',
    )
    const quiet = within(dialog).getByRole('spinbutton', { name: 'Ruhezeit in Minuten' })
    await user.clear(quiet)
    await user.type(quiet, '10')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(api.find('POST', '/api/automations')).toHaveLength(1))
    expect(api.find('POST', '/api/automations')[0]?.body).toEqual({
      agent_id: HILDA_AGENT.id,
      place: { type: 'channel', conversation_id: 'c-1' },
      instruction: 'Ordne ein.',
      schedule: {
        kind: 'event',
        event_type: 'ticket.created',
        quiet_seconds: 600,
        filter_tag_id: 't-bug',
        filter_ticket_kind: 'bug',
      },
    })
  })

  test('outside a space I manage there is no event rule to make', async () => {
    formApi()
    const { dialog } = await openForm()
    expect(within(dialog).queryByRole('radio', { name: /Ereignis-Regel/ })).toBeNull()
  })
})

describe('changing an automation', () => {
  test('its kind stays; a stale version reloads and keeps what was typed', async () => {
    const automation = makeAutomation({ version: 2, instruction: 'Alt' })
    let current = automation
    const api = mockApi({
      ...shellRoutes(me),
      [`GET /api/automations/${automation.id}`]: () => current,
      [`GET /api/automations/${automation.id}/firings`]: page([]),
      'POST /api/automations/preview': { terms: TERMS },
      [`PATCH /api/automations/${automation.id}`]: (call: { body: { version: number } }) =>
        call.body.version === 2
          ? apiError(409, 'automation.version_conflict', 'stale', { current_version: 3 })
          : { ...automation, version: 4, instruction: 'Neu' },
    })
    const { user } = await renderApp(`/automations/${automation.id}`)
    await user.click(await screen.findByRole('button', { name: 'Bearbeiten' }))
    const dialog = await screen.findByRole('dialog', { name: 'Aufgabe bearbeiten' })
    expect(within(dialog).queryByRole('radio')).toBeNull()
    expect(
      within(dialog).getByText('Die Art lässt sich nach dem Anlegen nicht mehr ändern.'),
    ).toBeInTheDocument()
    const text = within(dialog).getByRole('textbox', { name: 'Auftrag' })
    await user.clear(text)
    await user.type(text, 'Neu')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    current = { ...automation, version: 3 }
    await user.click(await within(dialog).findByRole('button', { name: 'Aktuelle Fassung laden' }))
    expect(within(dialog).getByRole('textbox', { name: 'Auftrag' })).toHaveValue('Neu')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(api.find('PATCH', `/api/automations/${automation.id}`).map((c) => c.body)).toEqual([
      { version: 2, instruction: 'Neu' },
      { version: 3, instruction: 'Neu' },
    ])
  })
})
