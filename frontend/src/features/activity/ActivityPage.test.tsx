import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { makeMe, mockApi, page } from '@/test/api'
import { makeActivity, makeConversation, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'

describe('activity', () => {
  test('entries lead into their conversation; done and read-all are sent', async () => {
    const channel = makeConversation({ id: 'c-1' })
    const entry = makeActivity()
    const api = mockApi({
      ...shellRoutes(makeMe([])),
      'GET /api/activity': page([entry]),
      'POST /api/activity/:id/read': { status: 204 },
      'POST /api/activity/:id/done': { status: 204 },
      'POST /api/activity/read-all': { status: 204 },
      'GET /api/conversations/:id': channel,
      'GET /api/conversations/:id/messages': page([]),
      'GET /api/spaces/:id': { status: 404, body: { error: { code: 'space.not_found' } } },
    })
    const { user, router } = await renderApp('/activity')
    const item = (await screen.findByText('Lea Löwe')).closest('li')!
    expect(item).toHaveTextContent('hat dich in # allgemein erwähnt')
    expect(item).toHaveTextContent('Hallo @Mia Muster')
    await user.click(
      within(item).getByRole('button', { name: 'Eintrag von Lea Löwe als erledigt markieren' }),
    )
    await user.click(screen.getByRole('button', { name: 'Alle als gelesen markieren' }))
    await waitFor(() => expect(api.find('POST', '/api/activity/read-all')).toHaveLength(1))
    expect(api.find('POST', `/api/activity/${entry.id}/done`)).toHaveLength(1)

    await user.click(within(item).getByRole('button', { name: 'Öffnen' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/c/c-1'))
    expect(router.state.location.search).toEqual({ message: entry.message_id })
    expect(api.find('POST', `/api/activity/${entry.id}/read`)).toHaveLength(1)
  })

  test("an agent's release request carries the AI mark", async () => {
    const entry = makeActivity({
      reason: 'approval',
      author: { type: 'agent', id: 'hilda', name: 'Hilda' },
      snippet: 'propose_page_change: page_id=p-1',
    })
    mockApi({ ...shellRoutes(makeMe(['ai.use'])), 'GET /api/activity': page([entry]) })
    await renderApp('/activity')
    const item = (await screen.findByText('Hilda')).closest('li')!
    expect(within(item).getByText('Von einer KI geschrieben')).toBeInTheDocument()
  })

  test("an agent's skill proposal names where it belongs and opens the proposal", async () => {
    const entry = makeActivity({
      reason: 'skill_proposal',
      conversation: null,
      message_id: null,
      author: { type: 'agent', id: 'hilda', name: 'Hilda' },
      snippet: '',
      skill_proposal: { id: 'sp-1', space_id: null },
    })
    mockApi({
      ...shellRoutes(makeMe(['ai.use'])),
      'GET /api/activity': page([entry]),
      'POST /api/activity/:id/read': { status: 204 },
      'GET /api/skill-proposals/:id': { status: 404, body: { error: { code: 'x' } } },
    })
    const { user, router } = await renderApp('/activity')
    const item = (await screen.findByText('Hilda')).closest('li')!
    expect(item).toHaveTextContent(
      'hat einen Skill vorgeschlagen oder einen Vorschlag entschieden (organisationsweit)',
    )
    expect(within(item).getByText('Von einer KI geschrieben')).toBeInTheDocument()
    await user.click(within(item).getByRole('button', { name: 'Öffnen' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/skill-proposals/sp-1'))
  })

  test('a paused automation names its agent and why it was paused', async () => {
    const entry = makeActivity({
      reason: 'automation',
      conversation: null,
      message_id: null,
      author: { type: 'agent', id: 'hilda', name: 'Hilda' },
      snippet: '',
      automation: { id: 'au-1', paused_reason: 'owner' },
    })
    mockApi({ ...shellRoutes(makeMe(['ai.use'])), 'GET /api/activity': page([entry]) })
    await renderApp('/activity')
    const item = (await screen.findByText('Hilda')).closest('li')!
    expect(item).toHaveTextContent(
      'hat eine Aufgabe angehalten (die Eigentümerin darf sie nicht mehr ausführen)',
    )
    expect(within(item).getByText('Von einer KI geschrieben')).toBeInTheDocument()
  })

  test('a proposal for a new page at the top level opens the proposal', async () => {
    const entry = makeActivity({
      reason: 'proposal',
      conversation: null,
      message_id: null,
      snippet: '',
      proposal: { id: 'pr-1', space_id: 'space-1' },
    })
    mockApi({
      ...shellRoutes(makeMe([])),
      'GET /api/activity': page([entry]),
      'POST /api/activity/:id/read': { status: 204 },
      'GET /api/spaces/:id': { status: 404, body: { error: { code: 'space.not_found' } } },
    })
    const { user, router } = await renderApp('/activity')
    const item = (await screen.findByText('Lea Löwe')).closest('li')!
    await user.click(within(item).getByRole('button', { name: 'Öffnen' }))
    await waitFor(() =>
      expect(router.state.location.pathname).toBe('/spaces/space-1/proposals/pr-1'),
    )
  })

  test('nothing for me says so', async () => {
    mockApi({ ...shellRoutes(makeMe([])), 'GET /api/activity': page([]) })
    await renderApp('/activity')
    expect(await screen.findByText('Nichts Neues für dich.')).toBeInTheDocument()
  })

  test('an assignment names who assigned which ticket and opens the ticket', async () => {
    const entry = makeActivity({
      reason: 'assignment',
      conversation: {
        id: 'c-9',
        kind: 'thread_ticket',
        name: null,
        space_id: 'space-1',
        page_id: null,
        ticket_number: 42,
      },
      author: { type: 'user', id: 'jan', name: 'Jan Jansen' },
      snippet: '',
    })
    mockApi({
      ...shellRoutes(makeMe([])),
      'GET /api/activity': page([entry]),
      'POST /api/activity/:id/read': { status: 204 },
      'GET /api/tickets/:number': { status: 404, body: { error: { code: 'ticket.not_found' } } },
    })
    const { user, router } = await renderApp('/activity')
    const item = (await screen.findByText('Jan Jansen')).closest('li')!
    expect(item).toHaveTextContent('Jan Jansen hat dir HC-42 zugewiesen')
    await user.click(within(item).getByRole('button', { name: 'Öffnen' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/tickets/42'))
    expect(router.state.location.search).toEqual({ message: entry.message_id })
  })
})
