import { screen, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { makeMe, mockApi, page } from '@/test/api'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { makeEvent, makeRun } from '@/test/runs'

const TOOL = 'ext_0123456789ab_create_issue'
const UNKNOWN = 'external_outcome_unknown: this call was sent to the external server …'

function call(seq: number, callId: string, text: string, duration = 0) {
  return makeEvent({
    kind: 'tool_call',
    seq,
    duration_ms: duration,
    content: {
      step: 1,
      call_id: callId,
      name: TOOL,
      args: { repo: 'acme/app', title: 'Fehler' },
      source: 'mcp',
      attrs: { server: 'GitHub', tool: 'create_issue' },
      text,
    },
  })
}

describe('a run with external calls', () => {
  test('one entry per call with its latest state, "outcome unknown" included', async () => {
    const me = makeMe(['directory.read', 'ai.use'])
    const run = makeRun({ stop_reason: 'completed' })
    mockApi({
      ...shellRoutes(me),
      'GET /api/runs/:id': run,
      'GET /api/runs/:id/events': page([
        makeEvent({
          kind: 'model_call',
          seq: 1,
          content: {
            step: 1,
            tool_calls: [
              { id: 'c1', name: TOOL, args: {} },
              { id: 'c2', name: TOOL, args: {} },
            ],
          },
        }),
        call(2, 'c1', UNKNOWN),
        call(3, 'c1', '{"number": 42}', 812),
        call(4, 'c2', UNKNOWN),
        makeEvent({ kind: 'stop', seq: 5, content: { reason: 'completed', detail: null } }),
      ]),
    })
    await renderApp(`/runs/${run.id}`)
    const steps = await screen.findByRole('list', { name: 'Schritte des Laufs' })
    expect(within(steps).getByText('Ruft auf: create_issue (extern), create_issue (extern)'))
    const entries = within(steps).getAllByText('GitHub · create_issue')
    expect(entries).toHaveLength(2)
    expect(within(steps).getAllByText('Externes Werkzeug')).toHaveLength(2)
    expect(within(steps).getByText('812 ms')).toBeInTheDocument()
    expect(within(steps).getAllByText(/Ausgang unbekannt/)).toHaveLength(1)
    expect(within(steps).getByText(/nicht noch einmal gesendet/)).toBeInTheDocument()
  })

  test('a call still on its way is shown as being sent', async () => {
    const me = makeMe(['directory.read', 'ai.use'])
    const run = makeRun({ state: 'running', stop_reason: null, finished_at: null })
    mockApi({
      ...shellRoutes(me),
      'GET /api/runs/:id': run,
      'GET /api/runs/:id/events': page([call(1, 'c1', UNKNOWN)]),
    })
    await renderApp(`/runs/${run.id}`)
    const steps = await screen.findByRole('list', { name: 'Schritte des Laufs' })
    expect(within(steps).getByText(/Wird an den externen Server gesendet/)).toBeInTheDocument()
    expect(within(steps).queryByText(/Ausgang unbekannt/)).toBeNull()
  })

  test('a run held back by a personal connector says why', async () => {
    const me = makeMe(['directory.read', 'ai.use'])
    const run = makeRun({ stop_reason: 'policy_blocked' })
    mockApi({
      ...shellRoutes(me),
      'GET /api/runs/:id': run,
      'GET /api/runs/:id/events': page([
        makeEvent({
          kind: 'stop',
          seq: 1,
          content: { reason: 'policy_blocked', detail: 'personal_connector' },
        }),
      ]),
    })
    await renderApp(`/runs/${run.id}`)
    const steps = await screen.findByRole('list', { name: 'Schritte des Laufs' })
    expect(
      within(steps).getByText(
        /mit dem persönlichen Zugang der fragenden Person zu einem externen Server gelesen/,
      ),
    ).toBeInTheDocument()
  })
})
