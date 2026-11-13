import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { type Call, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { makeTicket, makeTicketSummary } from '@/test/tickets'

const team = makeSpace({ id: 'space-1', name: 'Projekt Apfel', my_role: 'editor' })
const open = makeSpace({ id: 'space-2', name: 'Handbuch', my_role: 'viewer' })

function listApi(spaces = [team, open], extra = {}) {
  return mockApi({
    ...shellRoutes(makeMe([]), spaces),
    ...extra,
    'GET /api/tickets/counts': { assigned_open: 120 },
    'GET /api/tickets': (call: Call) =>
      call.query.get('assignee') === 'me'
        ? page([makeTicketSummary({ title: 'Meins', number: 1 })])
        : page([
            makeTicketSummary({ title: 'Meins', number: 1 }),
            makeTicketSummary({ title: 'Von Jan', number: 2, space_id: 'space-2' }),
          ]),
  })
}

describe('ticket list', () => {
  test('starts with my unfinished tickets; "all" and every filter go into the address', async () => {
    const api = listApi()
    const { router, user } = await renderApp('/tickets')
    expect(await screen.findByRole('link', { name: /HC-1\s*Meins/ })).toBeInTheDocument()
    const first = api.find('GET', '/api/tickets')[0]!
    expect(first.query.get('assignee')).toBe('me')
    expect(first.query.getAll('status_category')).toEqual(['open', 'active', 'review'])

    await user.click(screen.getByRole('button', { name: 'Alle Tickets' }))
    expect(await screen.findByRole('link', { name: /HC-2\s*Von Jan/ })).toBeInTheDocument()
    expect(router.state.location.search).toEqual({ who: 'all' })
    const rows = screen.getByRole('link', { name: /HC-2/ }).closest('li')!
    expect(within(rows).getByText('Handbuch')).toBeInTheDocument() // the space of a row

    await user.selectOptions(screen.getByRole('combobox', { name: 'Art' }), 'Fehler')
    await waitFor(() => expect(router.state.location.search).toEqual({ who: 'all', kind: 'bug' }))
    expect(api.find('GET', '/api/tickets').at(-1)!.query.get('kind')).toBe('bug')
    expect(api.find('GET', '/api/tickets').at(-1)!.query.get('assignee')).toBeNull()
  })

  test('the address restores the filters', async () => {
    const api = listApi()
    await renderApp('/tickets?who=all&state=done&space=space-1&q=Login')
    await screen.findByRole('link', { name: /HC-2/ })
    const asked = api.find('GET', '/api/tickets')[0]!
    expect(asked.query.getAll('status_category')).toEqual(['done'])
    expect(asked.query.get('q')).toBe('Login')
    // "space-1" is no id: dropped from the address, so it is not asked.
    expect(asked.query.get('space_id')).toBeNull()
  })

  test('the sidebar counts my unfinished tickets, capped at 99+', async () => {
    listApi()
    await renderApp('/tickets')
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
    const work = within(nav.querySelector('[data-section="work"]') as HTMLElement)
    const link = await work.findByRole('link', { name: /Tickets/ })
    await waitFor(() => expect(link).toHaveTextContent('99+'))
    expect(link).toHaveTextContent('120 offene Tickets für dich')
  })

  test('new ticket: only with a space one may create in; opens the new ticket', async () => {
    const created = makeTicket({ number: 77, title: 'Neuer Fehler', kind: 'bug' })
    const api = listApi([team, open], {
      'POST /api/spaces/:id/tickets': { status: 201, body: created },
      'GET /api/tickets/:number': created,
      'GET /api/spaces/:id': team,
    })
    const { router, user } = await renderApp('/tickets')
    await user.click(await screen.findByRole('button', { name: 'Neues Ticket' }))
    const dialog = await screen.findByRole('dialog', { name: 'Neues Ticket' })
    // One space to create in (the viewer space is not offered): nothing to choose.
    expect(within(dialog).queryByRole('combobox', { name: 'Bereich' })).toBeNull()
    await user.type(within(dialog).getByRole('textbox', { name: 'Titel' }), 'Neuer Fehler')
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Art' }), 'Fehler')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/tickets/77'))
    const posted = api.find('POST', '/api/spaces/space-1/tickets')[0]!
    expect(posted.body).toMatchObject({ title: 'Neuer Fehler', kind: 'bug', priority: 'normal' })
  })

  test('no space to create in: no "new ticket"', async () => {
    listApi([open])
    await renderApp('/tickets')
    await screen.findByRole('link', { name: /HC-1/ })
    expect(screen.queryByRole('button', { name: 'Neues Ticket' })).toBeNull()
  })
})
