// Module review M8 2, finding G1: a run whose history held messages marked personal
// starts marked; its journal says so with a `mark` event, which the run page shows
// as its own row (not as a stop).
import { screen, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import { makeMe, mockApi, page } from '@/test/api'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { makeEvent, makeRun } from '@/test/runs'
import { buildTimeline } from './timeline'

const mark = makeEvent({
  kind: 'mark',
  seq: 1,
  content: { read: { personal: true }, source: 'conversation' },
})

test('a mark is a row of its own in the timeline', () => {
  const items = buildTimeline([mark], makeRun())
  expect(items.map((item) => item.kind)).toEqual(['mark'])
})

test('the run page says that the history held personal content', async () => {
  const run = makeRun()
  mockApi({
    ...shellRoutes(makeMe(['directory.read', 'ai.use'])),
    'GET /api/runs/:id': run,
    'GET /api/runs/:id/events': page([mark]),
  })
  await renderApp(`/runs/${run.id}`)
  const steps = await screen.findByRole('list', { name: 'Schritte des Laufs' })
  expect(within(steps).getByText('Persönliches im Verlauf')).toBeInTheDocument()
  expect(
    within(steps).getByText(
      'Der Verlauf, den der Lauf bekam, enthält Nachrichten mit dem, was die fragende Person über ihren eigenen Zugang gelesen hat. Der Lauf trägt deshalb ihre Markierung: Was er daraus schreibt, bleibt bei ihr.',
    ),
  ).toBeInTheDocument()
  expect(within(steps).queryByText('Ende')).not.toBeInTheDocument()
})
