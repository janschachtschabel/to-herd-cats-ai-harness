import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Permission } from '@/lib/api'
import { apiError, makeMe, mockApi, page } from '@/test/api'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { HILDA, makeEvent, makeRun } from '@/test/runs'
import { buildTimeline } from './timeline'

function runsApi(permissions: Permission[], extra: Record<string, object> = {}) {
  const me = makeMe(['directory.read', ...permissions])
  const api = mockApi({ ...shellRoutes(me), ...extra })
  return { api, me }
}

describe('my runs', () => {
  test('lists my runs with state, place, steps and cost; filters go to the API', async () => {
    const done = makeRun()
    const stopped = makeRun({
      stop_reason: 'cancelled',
      place: {
        kind: 'channel',
        conversation_id: 'c-2',
        space_id: 's',
        page_id: null,
        ticket_number: null,
      },
    })
    const { api } = runsApi(['ai.use'], { 'GET /api/runs': page([done, stopped]) })
    const { user } = await renderApp('/runs')
    const list = await screen.findByRole('list', { name: 'Läufe' })
    expect(within(list).getByRole('link', { name: 'Hilda · HC-7' })).toHaveAttribute(
      'href',
      `/runs/${done.id}`,
    )
    expect(within(list).getByText('Abgeschlossen')).toBeInTheDocument()
    expect(within(list).getByText('Hilda · Kanal')).toBeInTheDocument()
    expect(within(list).getByText('Der Lauf wurde abgebrochen.')).toBeInTheDocument()
    expect(within(list).getAllByText('2 Schritte')).toHaveLength(2)
    expect(within(list).getAllByText('Kosten 0,0123')).toHaveLength(2)

    await user.selectOptions(screen.getByRole('combobox', { name: 'Stopgrund' }), 'cancelled')
    await waitFor(() =>
      expect(api.find('GET', '/api/runs').at(-1)?.query.get('stop_reason')).toBe('cancelled'),
    )
  })

  test('the page is not there for people without AI or agent rights', async () => {
    runsApi([])
    await renderApp('/runs')
    expect(await screen.findByText(/nicht gefunden/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Meine Läufe' })).toBeNull()
  })

  test('an empty list says so', async () => {
    runsApi(['ai.use'], { 'GET /api/runs': page([]) })
    await renderApp('/runs')
    expect(await screen.findByText('Noch keine Läufe.')).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
    expect(within(nav).getByRole('link', { name: 'Meine Läufe' })).toBeInTheDocument()
  })
})

describe('the run page', () => {
  const events = [
    makeEvent({
      kind: 'model_call',
      content: {
        step: 1,
        text: 'Ich lese das Ticket.',
        tool_calls: [{ id: 'c1', name: 'read_ticket', args: { key: 'HC-7' } }],
      },
      tokens_in: 900,
      tokens_out: 40,
      duration_ms: 1500,
    }),
    makeEvent({
      kind: 'tool_call',
      content: {
        step: 1,
        call_id: 'c1',
        name: 'read_ticket',
        args: { key: 'HC-7' },
        source: 'ticket',
        text: 'HC-7: Urlaubsliste prüfen',
      },
      duration_ms: 20,
    }),
    makeEvent({
      kind: 'tool_call',
      content: { step: 2, call_id: 'c2', name: 'search', source: 'wiki' },
      redacted: true,
    }),
  ]

  test('shows who, where, how it went, and its steps with folded details', async () => {
    const run = makeRun({ chain_depth: 1, attempt: 2, recoveries: 1 })
    runsApi(['ai.use'], {
      'GET /api/runs/:id': run,
      'GET /api/runs/:id/events': page([
        ...events,
        makeEvent({ kind: 'stop', seq: 0, content: { reason: 'completed', detail: null } }),
      ]),
    })
    const { user } = await renderApp(`/runs/${run.id}`)
    expect(await screen.findByRole('heading', { name: 'Lauf von Hilda' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'HC-7' })).toHaveAttribute('href', '/tickets/7')
    expect(screen.getByText('Jan Jansen')).toBeInTheDocument()
    expect(screen.getByText('2 Versuche, 1 Wiederaufnahmen')).toBeInTheDocument()
    expect(screen.getByText('1 Übergabe von Agent zu Agent')).toBeInTheDocument()
    expect(
      screen.getByText('1.200 ein (200 aus dem Zwischenspeicher), 300 aus'),
    ).toBeInTheDocument()
    expect(screen.getByText('0,0123')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Lauf abbrechen' })).toBeNull()

    const steps = await screen.findByRole('list', { name: 'Schritte des Laufs' })
    expect(within(steps).getByText('Modellschritt 1')).toBeInTheDocument()
    expect(within(steps).getByText('Ich lese das Ticket.')).toBeInTheDocument()
    expect(within(steps).getByText('Ruft auf: Ticket lesen')).toBeInTheDocument()
    expect(within(steps).getByText('Nicht für dich sichtbar.')).toBeInTheDocument()
    expect(within(steps).getByText('Der Lauf ist abgeschlossen.')).toBeInTheDocument()
    const result = within(steps).getByText('Ergebnis')
    expect(within(steps).getByText('HC-7: Urlaubsliste prüfen')).not.toBeVisible()
    await user.click(result)
    expect(within(steps).getByText('HC-7: Urlaubsliste prüfen')).toBeVisible()
  })

  test('a running run is cancelled after confirming; a finished one says so', async () => {
    let run = makeRun({ state: 'running', stop_reason: null, finished_at: null })
    let first = true
    const { api } = runsApi(['ai.use'], {
      'GET /api/runs/:id': () => run,
      'GET /api/runs/:id/events': page(events.slice(0, 2)),
      'POST /api/runs/:id/cancel': () => {
        if (first) {
          first = false
          return apiError(409, 'run.finished')
        }
        run = { ...run, cancel_requested: true }
        return run
      },
    })
    const { user } = await renderApp(`/runs/${run.id}`)
    await user.click(await screen.findByRole('button', { name: 'Lauf abbrechen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Lauf abbrechen?' })
    await user.click(within(dialog).getByRole('button', { name: 'Ja, Lauf abbrechen' }))
    expect(
      await within(dialog).findByText('Der Lauf ist schon zu Ende gegangen.'),
    ).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Ja, Lauf abbrechen' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(api.find('POST', `/api/runs/${run.id}/cancel`)).toHaveLength(2)
    expect(await screen.findByText(/Abbruch angefordert/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Lauf abbrechen' })).toBeNull()
  })

  test('a run one may not see is not found, in words', async () => {
    runsApi(['ai.use'], { 'GET /api/runs/:id': apiError(404, 'run.not_found') })
    await renderApp('/runs/00000000-0000-7000-8000-000000000999')
    expect(
      await screen.findByText('Diesen Lauf gibt es nicht, oder du darfst ihn nicht sehen.'),
    ).toBeInTheDocument()
  })

  test("the agent's runs page names the agent and the asker of each run", async () => {
    runsApi(['ai.use'], { 'GET /api/agents/:id/runs': page([makeRun()]) })
    await renderApp(`/agents/${HILDA.id}/runs`)
    expect(await screen.findByRole('heading', { name: 'Läufe von Hilda' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'HC-7 · gefragt von Jan Jansen' })).toBeInTheDocument()
  })
})

describe('the timeline of a waiting run', () => {
  test('calls of the last step without a result wait', () => {
    const run = makeRun({ state: 'waiting', stop_reason: null })
    const items = buildTimeline(
      [
        makeEvent({
          content: {
            step: 1,
            tool_calls: [
              { id: 'a', name: 'read_page', args: {} },
              { id: 'b', name: 'update_page', args: {} },
            ],
          },
        }),
        makeEvent({ kind: 'tool_call', content: { step: 1, call_id: 'a', name: 'read_page' } }),
      ],
      run,
    )
    expect(items.map((i) => i.kind)).toEqual(['model', 'tool', 'waiting'])
    expect(buildTimeline([], makeRun()).length).toBe(0)
  })
})
