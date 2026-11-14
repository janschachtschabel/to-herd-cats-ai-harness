import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test, vi } from 'vitest'
import { apiError, makeMe, mockApi, page } from '@/test/api'
import { ALL_ABILITIES, makeAutomation, makeFiring } from '@/test/automations'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'

vi.mock('@/features/automations/zoned', async (original) => ({
  ...(await original<typeof import('./zoned')>()),
  viewerZone: () => 'Europe/Berlin',
}))

const me = makeMe(['directory.read', 'ai.use'])

function detailApi(
  automation: ReturnType<typeof makeAutomation>,
  extra: Record<string, unknown> = {},
) {
  return mockApi({
    ...shellRoutes(me),
    [`GET /api/automations/${automation.id}`]: automation,
    [`GET /api/automations/${automation.id}/firings`]: page([]),
    ...(extra as Record<string, object>),
  })
}

describe('one automation', () => {
  test('shows what it does, where, when, and its log with every outcome in words', async () => {
    const automation = makeAutomation({
      kind: 'heartbeat',
      cron: null,
      interval_minutes: 30,
      active_days: [1, 2, 3, 4, 5],
      active_from: '09:00:00',
      active_until: '17:00:00',
      instruction: 'Sieh nach offenen Tickets.\nMelde nur, was neu ist.',
      place: {
        type: 'channel',
        conversation_id: 'c-9',
        space_id: 's-1',
        name: 'support',
        ticket_number: null,
      },
      upcoming: ['2026-11-16T08:00:00Z', '2026-11-16T08:30:00Z'],
    })
    const started = makeFiring({ run_id: 'run-7' })
    const firings = [
      started,
      makeFiring({ outcome: 'started', heartbeat_ok: true }),
      makeFiring({ outcome: 'skipped_busy', run_id: null }),
      makeFiring({ outcome: 'skipped_off_hours', run_id: null }),
      makeFiring({ outcome: 'skipped_policy', run_id: null }),
      makeFiring({ outcome: 'skipped_paused_agent', run_id: null }),
      makeFiring({ outcome: 'skipped_depth', run_id: null }),
    ]
    const api = detailApi(automation, {
      [`GET /api/automations/${automation.id}/firings`]: (call: { query: URLSearchParams }) =>
        call.query.get('cursor')
          ? page([makeFiring({ outcome: 'skipped_budget', run_id: null })])
          : page(firings, 'more'),
    })
    const { user } = await renderApp(`/automations/${automation.id}`)
    expect(
      await screen.findByRole('heading', { name: 'Sieh nach offenen Tickets.' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Melde nur, was neu ist\./)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Kanal #support' })).toHaveAttribute('href', '/c/c-9')
    expect(screen.getByText('Alle 30 Minuten, Mo–Fr, 09:00–17:00')).toBeInTheDocument()
    expect(screen.getByText('Zeitzone Europe/Berlin')).toBeInTheDocument()
    const upcoming = screen.getByRole('list', { name: 'Die nächsten Termine' })
    expect(
      within(upcoming)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(['16.11.2026, 09:00', '16.11.2026, 09:30'])

    const log = screen.getByRole('list', { name: 'Protokoll der Termine' })
    const rows = within(log).getAllByRole('listitem')
    expect(within(rows[0]!).getByText('Gestartet')).toBeInTheDocument()
    expect(within(rows[0]!).getByRole('link', { name: 'Lauf ansehen' })).toHaveAttribute(
      'href',
      '/runs/run-7',
    )
    expect(within(log).getByText('Nichts zu melden (HEARTBEAT_OK, still)')).toBeInTheDocument()
    expect(
      within(log).getByText('Übersprungen: Der vorige Lauf arbeitete noch'),
    ).toBeInTheDocument()
    expect(within(log).getByText('Übersprungen: außerhalb der aktiven Stunden')).toBeInTheDocument()
    expect(
      within(log).getByText('Übersprungen: Der Ort war archiviert oder für diese KI gesperrt'),
    ).toBeInTheDocument()
    expect(
      within(log).getByText('Übersprungen: Der Agent war angehalten oder nicht verfügbar'),
    ).toBeInTheDocument()
    expect(
      within(log).getByText('Übersprungen: Die Kette war zu tief (Tiefe 3)'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Mehr laden' }))
    expect(
      await within(log).findByText('Übersprungen: Ein Tagesbudget war erreicht'),
    ).toBeInTheDocument()
    expect(
      api.find('GET', `/api/automations/${automation.id}/firings`).at(-1)?.query.get('cursor'),
    ).toBe('more')
  })

  test('one I may not see says so in words', async () => {
    mockApi({
      ...shellRoutes(me),
      'GET /api/automations/gone': apiError(404, 'automation.not_found'),
      'GET /api/automations/gone/firings': apiError(404, 'automation.not_found'),
    })
    await renderApp('/automations/gone')
    expect(
      await screen.findByText('Diese Aufgabe gibt es nicht, oder du darfst sie nicht sehen.'),
    ).toBeInTheDocument()
  })

  test('its owner may edit, pause, run now and delete it; nothing else is offered', async () => {
    const automation = makeAutomation()
    detailApi(automation)
    await renderApp(`/automations/${automation.id}`)
    const actions = await screen.findByRole('group', { name: 'Aktionen' })
    expect(
      within(actions)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['Anhalten', 'Jetzt ausführen', 'Löschen'])
  })

  test('pausing names the version read; a stale one offers to reload', async () => {
    const automation = makeAutomation({ version: 3 })
    let current = automation
    const paused = {
      ...automation,
      version: 5,
      state: 'paused' as const,
      paused_reason: 'manual' as const,
      abilities: { ...ALL_ABILITIES, pause: false, resume: true },
    }
    const api = detailApi(automation, {
      [`GET /api/automations/${automation.id}`]: () => current,
      [`POST /api/automations/${automation.id}/pause`]: (call: { body: { version: number } }) => {
        if (call.body.version === 3) {
          return apiError(409, 'automation.version_conflict', 'stale', { current_version: 4 })
        }
        current = paused
        return paused
      },
    })
    const { user } = await renderApp(`/automations/${automation.id}`)
    await user.click(await screen.findByRole('button', { name: 'Anhalten' }))
    current = { ...automation, version: 4 }
    await user.click(await screen.findByRole('button', { name: 'Aktuelle Fassung laden' }))
    await user.click(await screen.findByRole('button', { name: 'Anhalten' }))
    expect(await screen.findByText('Von Hand angehalten')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Fortsetzen' })).toBeInTheDocument()
    expect(api.find('POST', `/api/automations/${automation.id}/pause`).map((c) => c.body)).toEqual([
      { version: 3 },
      { version: 4 },
    ])
  })

  test('run now tells how the term went', async () => {
    const automation = makeAutomation()
    detailApi(automation, {
      [`POST /api/automations/${automation.id}/run`]: {
        ...automation,
        last_run: {
          firing_id: 'f',
          due_at: '2026-11-15T10:00:00Z',
          fired_at: '2026-11-15T10:00:00Z',
          outcome: 'skipped_busy',
          heartbeat_ok: false,
          run_id: null,
          run_state: null,
          stop_reason: null,
        },
      },
    })
    const { user } = await renderApp(`/automations/${automation.id}`)
    await user.click(await screen.findByRole('button', { name: 'Jetzt ausführen' }))
    expect(
      await screen.findByText('Termin ausgelöst: Übersprungen: Der vorige Lauf arbeitete noch'),
    ).toBeInTheDocument()
  })

  test('deleting asks first, names the version and goes back to my automations', async () => {
    const automation = makeAutomation({ version: 2 })
    const api = detailApi(automation, {
      [`DELETE /api/automations/${automation.id}`]: { status: 204 },
      'GET /api/automations': page([]),
    })
    const { user, router } = await renderApp(`/automations/${automation.id}`)
    await user.click(await screen.findByRole('button', { name: 'Löschen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Aufgabe löschen?' })
    expect(
      within(dialog).getByText(/Ihre bisherigen Läufe bleiben als Verlauf erhalten/),
    ).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Löschen' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/automations'))
    expect(api.find('DELETE', `/api/automations/${automation.id}`)[0]?.query.get('version')).toBe(
      '2',
    )
  })

  test('paused because its owner may not run it: a manager takes it over, told what it means', async () => {
    const automation = makeAutomation({
      state: 'paused',
      paused_reason: 'owner',
      version: 6,
      abilities: {
        edit: false,
        pause: false,
        resume: false,
        delete: true,
        run: false,
        take_over: true,
      },
    })
    const taken = {
      ...automation,
      state: 'active' as const,
      paused_reason: null,
      version: 7,
      owner: { id: me.user.id, name: me.user.name },
      abilities: ALL_ABILITIES,
    }
    let current = automation
    const api = detailApi(automation, {
      [`GET /api/automations/${automation.id}`]: () => current,
      [`POST /api/automations/${automation.id}/take-over`]: () => {
        current = taken
        return taken
      },
    })
    const { user } = await renderApp(`/automations/${automation.id}`)
    expect(
      await screen.findByText(
        /Die Eigentümerin darf diese Aufgabe nicht mehr ausführen; fortsetzen geht deshalb nicht/,
      ),
    ).toBeInTheDocument()
    const actions = screen.getByRole('group', { name: 'Aktionen' })
    expect(
      within(actions)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['Übernehmen', 'Löschen'])
    await user.click(within(actions).getByRole('button', { name: 'Übernehmen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Aufgabe übernehmen?' })
    expect(within(dialog).getByText(/läuft dann mit deinen Rechten/)).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Übernehmen' }))
    expect(await screen.findByText('Aktiv')).toBeInTheDocument()
    expect(api.find('POST', `/api/automations/${automation.id}/take-over`)[0]?.body).toEqual({
      version: 6,
    })
  })

  test('a resume refused because the owner may no longer run it says why', async () => {
    const automation = makeAutomation({
      state: 'paused',
      paused_reason: 'manual',
      abilities: { ...ALL_ABILITIES, pause: false, resume: true },
    })
    detailApi(automation, {
      [`POST /api/automations/${automation.id}/resume`]: apiError(409, 'automation.owner_unable'),
    })
    const { user } = await renderApp(`/automations/${automation.id}`)
    await user.click(await screen.findByRole('button', { name: 'Fortsetzen' }))
    expect(
      await screen.findByText(
        'Die Eigentümerin darf diese Aufgabe nicht mehr ausführen. Wer sie selbst anlegen dürfte, kann sie übernehmen.',
      ),
    ).toBeInTheDocument()
  })
})
