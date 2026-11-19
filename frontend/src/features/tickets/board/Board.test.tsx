import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Board, SpaceRole, TicketSummary } from '@/lib/api'
import { apiError, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { makeTicket, makeTicketSummary, STATUSES, statusRef } from '@/test/tickets'
import { dropTarget } from './dnd'
import { moveCard } from './queries'

const login = makeTicketSummary({ number: 42, version: 3 })
const export_ = makeTicketSummary({
  number: 43,
  title: 'Export bricht ab',
  status: statusRef(STATUSES[1]!),
})

function makeBoard(...tickets: TicketSummary[]): Board {
  return {
    columns: STATUSES.map((status) => {
      const items = tickets.filter((ticket) => ticket.status.id === status.id)
      return { status: statusRef(status), count: items.length, items, next_cursor: null }
    }),
  }
}

function boardApi(
  role: SpaceRole,
  extra = {},
  board: () => Board = () => makeBoard(login, export_),
) {
  const space = makeSpace({ id: 'space-1', name: 'Projekt Apfel', my_role: role })
  return mockApi({
    ...shellRoutes(makeMe(['directory.read']), [space]),
    'GET /api/spaces/:id': space,
    'GET /api/spaces/:id/pages/tree': page([]),
    'GET /api/tags': page([]),
    'GET /api/spaces/:id/epics': page([]),
    'GET /api/spaces/:id/board': () => board(),
    ...extra,
  })
}

const column = (name: string) => screen.getByRole('region', { name: new RegExp(`^${name}`) })

describe('board', () => {
  test('shows the statuses as columns with their cards and counts', async () => {
    boardApi('viewer')
    await renderApp('/spaces/space-1/board')
    const open = await screen.findByRole('region', { name: /^Neu/ })
    expect(within(open).getByRole('link', { name: /HC-42 Login schlägt fehl/ })).toBeVisible()
    expect(within(open).getByText('1 Ticket')).toBeInTheDocument()
    expect(within(column('In Arbeit')).getByRole('link', { name: /HC-43/ })).toBeVisible()
    expect(within(column('Erledigt')).getByText('0 Tickets')).toBeInTheDocument()
    // A viewer moves nothing: neither grip nor status menu.
    expect(screen.queryByRole('button', { name: 'HC-42 verschieben' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Status von HC-42 ändern' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Neues Ticket' })).toBeNull()
  })

  test('an editor moves a card through its menu: at once, with the version read', async () => {
    const moved = { ...login, status: statusRef(STATUSES[2]!), version: 4 }
    let patched = false
    const api = boardApi(
      'editor',
      {
        'PATCH /api/tickets/:number': () => {
          patched = true
          return makeTicket(moved)
        },
      },
      () => (patched ? makeBoard(moved, export_) : makeBoard(login, export_)),
    )
    const { user } = await renderApp('/spaces/space-1/board')
    expect(await screen.findByRole('button', { name: 'HC-42 verschieben' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Status von HC-42 ändern' }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'Zur Prüfung' }))
    await waitFor(() =>
      expect(within(column('Zur Prüfung')).getByRole('link', { name: /HC-42/ })).toBeVisible(),
    )
    expect(within(column('Neu')).queryByRole('link', { name: /HC-42/ })).toBeNull()
    // The card moved to another column: the focus goes with it, back to its menu button.
    await waitFor(() =>
      expect(
        within(column('Zur Prüfung')).getByRole('button', { name: 'Status von HC-42 ändern' }),
      ).toHaveFocus(),
    )
    const sent = api.find('PATCH', '/api/tickets/42')[0]!
    expect(sent.body).toEqual({ status_id: STATUSES[2]!.id, version: 3 })
  })

  test('a refused move (changed in the meantime) puts the card back and says so', async () => {
    let refused = false
    boardApi('editor', {
      'PATCH /api/tickets/:number': () => {
        refused = true
        return apiError(409, 'ticket.version_conflict')
      },
    })
    const { user } = await renderApp('/spaces/space-1/board')
    await user.click(await screen.findByRole('button', { name: 'Status von HC-42 ändern' }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'Erledigt' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Das Ticket wurde inzwischen geändert',
    )
    expect(refused).toBe(true)
    expect(within(column('Neu')).getByRole('link', { name: /HC-42/ })).toBeVisible()
    expect(within(column('Erledigt')).queryByRole('link', { name: /HC-42/ })).toBeNull()
  })

  test('the board offers its views; the tree stays with the wiki', async () => {
    boardApi('viewer')
    await renderApp('/spaces/space-1/board')
    const views = await screen.findByRole('navigation', { name: 'Ansichten des Bereichs' })
    expect(within(views).getByRole('link', { name: 'Board' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(views).getByRole('link', { name: 'Wiki' })).not.toHaveAttribute('aria-current')
    expect(within(views).getByRole('link', { name: 'Epics' })).toBeInTheDocument()
    // The space's calendar: the calendar page, filtered to it (plan M10).
    expect(within(views).getByRole('link', { name: 'Kalender' })).toHaveAttribute(
      'href',
      '/calendar?space=space-1',
    )
  })
})

describe('board moves', () => {
  const active = { id: login.id, data: { current: { ticket: login } } }

  test('a drop on another column is a move to its status', () => {
    const over = { id: STATUSES[1]!.id }
    expect(dropTarget({ active, over } as never)).toEqual({
      ticket: login,
      statusId: STATUSES[1]!.id,
    })
  })

  test('a drop on its own column or on nothing is no move', () => {
    expect(dropTarget({ active, over: { id: STATUSES[0]!.id } } as never)).toBeNull()
    expect(dropTarget({ active, over: null } as never)).toBeNull()
  })

  test('a moved card goes on top of its new column; the counts follow', () => {
    const board = moveCard(makeBoard(login, export_), login, STATUSES[1]!.id)
    const [open, active_] = board.columns
    expect(open!.items).toEqual([])
    expect(open!.count).toBe(0)
    expect(active_!.items.map((t) => t.number)).toEqual([42, 43])
    expect(active_!.items[0]!.status.id).toBe(STATUSES[1]!.id)
    expect(active_!.count).toBe(2)
  })
})
