import { render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { runSearch } from '@/app/router/aiRoutes'
import { stopText } from '@/features/agents/display'
import { RunStoppedNotice } from '@/features/agents/RunStoppedNotice'
import { Providers } from '@/app/providers'
import { createQueryClient } from '@/app/queryClient'
import i18n from '@/lib/i18n'
import { makeMe, mockApi, page } from '@/test/api'
import { makeMessage, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { makeEvent, makeRun } from '@/test/runs'

const t = i18n.t.bind(i18n)

describe('a run stopped by a daily budget', () => {
  test('is worded in German and English, never as the unknown reason', async () => {
    expect(stopText(t, 'budget')).toBe(
      'Das Tagesbudget für KI ist erreicht; der Lauf wurde vor dem nächsten Modellaufruf beendet.',
    )
    await i18n.changeLanguage('en')
    expect(stopText(t, 'budget')).toBe(
      'The daily AI budget is used up; the run stopped before its next model call.',
    )
  })

  test('the run lists offer it as a filter, and the address keeps it', async () => {
    expect(runSearch({ stop_reason: 'budget' })).toEqual({ stop_reason: 'budget' })
    const me = makeMe(['directory.read', 'ai.use'])
    const stopped = makeRun({ stop_reason: 'budget' })
    const api = mockApi({ ...shellRoutes(me), 'GET /api/runs': page([stopped]) })
    const { user } = await renderApp('/runs')
    const list = await screen.findByRole('list', { name: 'Läufe' })
    expect(within(list).getByText(/Das Tagesbudget für KI ist erreicht/)).toBeInTheDocument()
    await user.selectOptions(screen.getByRole('combobox', { name: 'Stopgrund' }), 'Tagesbudget')
    await waitFor(() =>
      expect(api.find('GET', '/api/runs').at(-1)?.query.get('stop_reason')).toBe('budget'),
    )
  })

  test('the run view names whose limit was reached', async () => {
    const me = makeMe(['directory.read', 'ai.use'])
    const run = makeRun({ stop_reason: 'budget' })
    mockApi({
      ...shellRoutes(me),
      'GET /api/runs/:id': run,
      'GET /api/runs/:id/events': page([
        makeEvent({ kind: 'stop', seq: 0, content: { reason: 'budget', detail: 'agent' } }),
      ]),
    })
    await renderApp(`/runs/${run.id}`)
    const steps = await screen.findByRole('list', { name: 'Schritte des Laufs' })
    expect(within(steps).getByText(/Das Tagesbudget für KI ist erreicht/)).toBeInTheDocument()
    expect(within(steps).getByText('Erreicht: das Tageslimit dieses Agenten.')).toBeInTheDocument()
  })

  test('the stop notice where the run answers says so', () => {
    const message = makeMessage({
      kind: 'system',
      author: null,
      body_md: '',
      system: {
        key: 'run.stopped',
        actor: { id: 'a1', name: 'Hilda', type: 'agent' },
        number: null,
        old: null,
        new: { value: 'budget', name: null },
      },
    })
    render(
      <Providers queryClient={createQueryClient()}>
        <RunStoppedNotice message={message} />
      </Providers>,
    )
    expect(screen.getByText('Hilda hat ohne Antwort aufgehört:')).toBeInTheDocument()
    expect(screen.getByText(/Das Tagesbudget für KI ist erreicht/)).toBeInTheDocument()
  })

  test('a notice held back for the person’s own connector says why', () => {
    const message = makeMessage({
      kind: 'system',
      author: null,
      body_md: '',
      system: {
        key: 'run.stopped',
        actor: { id: 'a1', name: 'Hilda', type: 'agent' },
        number: null,
        old: null,
        new: { value: 'policy_blocked', name: null },
        stop_detail: 'personal_connector',
      },
    })
    render(
      <Providers queryClient={createQueryClient()}>
        <RunStoppedNotice message={message} />
      </Providers>,
    )
    expect(screen.getByText(/mit dem persönlichen Zugang der fragenden Person/)).toBeInTheDocument()
  })
})
