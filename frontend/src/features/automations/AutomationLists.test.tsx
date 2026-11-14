import { screen, within } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import type { Permission } from '@/lib/api'
import { apiError, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { makeAutomation } from '@/test/automations'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'

vi.mock('@/features/automations/zoned', async (original) => ({
  ...(await original<typeof import('./zoned')>()),
  viewerZone: () => 'Europe/Berlin',
}))

function automationsApi(permissions: Permission[], extra: Record<string, unknown> = {}) {
  const me = makeMe(['directory.read', ...permissions])
  return mockApi({ ...shellRoutes(me), ...(extra as Record<string, object>) })
}

const daily = makeAutomation({
  last_run: {
    firing_id: 'f-1',
    due_at: '2026-11-15T08:00:00Z',
    fired_at: '2026-11-15T08:00:01Z',
    outcome: 'started',
    heartbeat_ok: false,
    run_id: 'run-1',
    run_state: 'done',
    stop_reason: 'completed',
  },
})
const heartbeat = makeAutomation({
  kind: 'heartbeat',
  state: 'paused',
  paused_reason: 'owner',
  instruction: 'Prüfe offene Tickets ohne Bearbeitung.\nUnd melde dich.',
  cron: null,
  time_zone: 'America/New_York',
  interval_minutes: 30,
  active_days: [1, 2, 3, 4, 5],
  active_from: '09:00:00',
  active_until: '17:00:00',
  next_due_at: '2026-11-16T14:00:00Z',
  place: {
    type: 'channel',
    conversation_id: 'c-1',
    space_id: 's-1',
    name: 'support',
    ticket_number: null,
  },
})
const once = makeAutomation({
  kind: 'once',
  state: 'done',
  cron: null,
  time_zone: null,
  next_due_at: null,
  upcoming: [],
  place: { type: 'ticket', conversation_id: 'c-2', space_id: 's-1', name: null, ticket_number: 7 },
  last_run: {
    firing_id: 'f-2',
    due_at: '2026-11-14T09:00:00Z',
    fired_at: '2026-11-14T09:00:00Z',
    outcome: 'skipped_budget',
    heartbeat_ok: false,
    run_id: null,
    run_state: null,
    stop_reason: null,
  },
})

describe('my automations', () => {
  test('people with AI find them in the navigation, each with its terms and state', async () => {
    automationsApi(['ai.use'], { 'GET /api/automations': page([daily, heartbeat, once]) })
    const { user } = await renderApp('/spaces')
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
    await user.click(within(nav).getByRole('link', { name: 'Meine Aufgaben' }))
    const list = await screen.findByRole('list', { name: 'Aufgaben' })
    const [first, second, third] = within(list).getAllByRole('listitem')

    expect(
      within(first!).getByRole('link', {
        name: 'Fasse zusammen, was gestern im Kanal besprochen wurde.',
      }),
    ).toHaveAttribute('href', `/automations/${daily.id}`)
    expect(within(first!).getByText('Wiederkehrend')).toBeInTheDocument()
    expect(within(first!).getByText('Täglich um 09:00')).toBeInTheDocument()
    expect(within(first!).getByText(/Direktnachricht mit Hilda/)).toBeInTheDocument()
    // The next term in my time, its zone named.
    expect(within(first!).getByText('16.11.2026, 09:00 (Europe/Berlin)')).toBeInTheDocument()
    expect(within(first!).getByText('Aktiv')).toBeInTheDocument()
    expect(within(first!).getByText(/Gestartet · Abgeschlossen/)).toBeInTheDocument()
    expect(within(first!).getByRole('link', { name: 'Lauf ansehen' })).toHaveAttribute(
      'href',
      '/runs/run-1',
    )

    expect(within(second!).getByText('Prüfe offene Tickets ohne Bearbeitung.')).toBeInTheDocument()
    expect(within(second!).getByText('Alle 30 Minuten, Mo–Fr, 09:00–17:00')).toBeInTheDocument()
    expect(within(second!).getByText(/Kanal #support/)).toBeInTheDocument()
    // My time, and the automation's own where it differs; paused, it waits for a resume.
    expect(
      within(second!).getByText(
        'nach dem Fortsetzen; fällig 16.11.2026, 15:00 (dort 09:00, America/New_York)',
      ),
    ).toBeInTheDocument()
    expect(
      within(second!).getByText('Angehalten: Wer sie besitzt, darf sie nicht mehr ausführen'),
    ).toBeInTheDocument()
    expect(within(second!).getByText('noch keiner')).toBeInTheDocument()

    expect(within(third!).getByText(/Ticket HC-7/)).toBeInTheDocument()
    expect(within(third!).getByText('Erledigt')).toBeInTheDocument()
    expect(within(third!).getByText('kein weiterer Termin')).toBeInTheDocument()
    expect(
      within(third!).getByText('Übersprungen: Ein Tagesbudget war erreicht'),
    ).toBeInTheDocument()
    expect(within(third!).queryByRole('link', { name: 'Lauf ansehen' })).toBeNull()
  })

  test('without AI: no entry in the navigation and the page is not found', async () => {
    const api = automationsApi([])
    await renderApp('/automations')
    expect(await screen.findByRole('heading', { name: 'Seite nicht gefunden' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Meine Aufgaben' })).toBeNull()
    expect(api.find('GET', '/api/automations')).toEqual([])
  })

  test('none yet says so; a failed list can be retried; more load on demand', async () => {
    let calls = 0
    automationsApi(['ai.use'], {
      'GET /api/automations': () => {
        calls += 1
        return calls === 1 ? apiError(500, 'internal') : page([])
      },
    })
    const { user } = await renderApp('/automations')
    await user.click(await screen.findByRole('button', { name: 'Erneut versuchen' }))
    expect(await screen.findByText('Du hast noch keine Aufgabe angelegt.')).toBeInTheDocument()
  })

  test('a long list loads the rest with "Mehr laden"', async () => {
    const api = automationsApi(['ai.use'], {
      'GET /api/automations': (call: { query: URLSearchParams }) =>
        call.query.get('cursor') ? page([once]) : page([daily], 'next'),
    })
    const { user } = await renderApp('/automations')
    await screen.findByText('Täglich um 09:00')
    await user.click(screen.getByRole('button', { name: 'Mehr laden' }))
    expect(await screen.findByText('Erledigt')).toBeInTheDocument()
    expect(api.find('GET', '/api/automations').at(-1)?.query.get('cursor')).toBe('next')
  })
})

describe('the automations of a space', () => {
  test('a tab of the space lists what the API shows, with an event rule', async () => {
    const space = makeSpace({ id: 's-1', my_role: 'admin' })
    const rule = makeAutomation({
      kind: 'event',
      cron: null,
      time_zone: null,
      next_due_at: null,
      upcoming: [],
      event_type: 'ticket.created',
      quiet_seconds: 300,
      owner: { id: 'u-2', name: 'Jan Jansen' },
      place: {
        type: 'channel',
        conversation_id: 'c-1',
        space_id: 's-1',
        name: 'eingang',
        ticket_number: null,
      },
    })
    automationsApi(['ai.use'], {
      'GET /api/spaces/s-1': space,
      'GET /api/spaces/:id/pages/tree': page([]),
      'GET /api/spaces/s-1/automations': page([rule]),
    })
    const { user } = await renderApp('/spaces/s-1')
    const tabs = await screen.findByRole('navigation', { name: 'Ansichten des Bereichs' })
    await user.click(within(tabs).getByRole('link', { name: 'Aufgaben' }))
    const list = await screen.findByRole('list', { name: 'Aufgaben' })
    expect(within(list).getByText('Ereignis-Regel')).toBeInTheDocument()
    expect(within(list).getByText('Bei: Ticket angelegt')).toBeInTheDocument()
    expect(within(list).getByText('bei jedem passenden Ereignis')).toBeInTheDocument()
    expect(within(list).getByText(/Gehört Jan Jansen/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Neue Aufgabe' })).toBeEnabled()
  })

  test('without AI the space has no such tab', async () => {
    automationsApi([], {
      'GET /api/spaces/s-1': makeSpace({ id: 's-1' }),
      'GET /api/spaces/:id/pages/tree': page([]),
    })
    await renderApp('/spaces/s-1')
    const tabs = await screen.findByRole('navigation', { name: 'Ansichten des Bereichs' })
    expect(within(tabs).queryByRole('link', { name: 'Aufgaben' })).toBeNull()
  })
})
