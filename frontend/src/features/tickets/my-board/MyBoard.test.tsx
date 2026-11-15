import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { MyBoard, MyCard } from '@/lib/api'
import { apiError, makeMe, makeSpace, mockApi } from '@/test/api'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { makeTicket, makeTicketSummary, STATUSES, statusRef } from '@/test/tickets'
import { categoryDrop } from './dnd'
import { moveMyCard } from './queries'

const CATEGORIES = ['open', 'active', 'review', 'done'] as const

const apple = makeSpace({ id: 'space-1', name: 'Projekt Apfel', my_role: 'editor' })
const pear = makeSpace({ id: 'space-2', name: 'Projekt Birne', my_role: 'viewer' })

const login: MyCard = {
  ...makeTicketSummary({ number: 42, version: 3 }),
  space_name: 'Projekt Apfel',
}
const report: MyCard = {
  ...makeTicketSummary({
    number: 7,
    title: 'Bericht lesen',
    space_id: 'space-2',
    status: statusRef(STATUSES[1]!),
  }),
  space_name: 'Projekt Birne',
}

function makeMyBoard(...cards: MyCard[]): MyBoard {
  return {
    columns: CATEGORIES.map((category) => {
      const items = cards.filter((card) => card.status.category === category)
      return { category, count: items.length, items, next_cursor: null }
    }),
  }
}

function myBoardApi(extra = {}, board: () => MyBoard = () => makeMyBoard(login, report)) {
  return mockApi({
    ...shellRoutes(makeMe(['directory.read']), [apple, pear]),
    'GET /api/spaces/:id': (_call: unknown, params: Record<string, string>) =>
      params.id === 'space-2' ? pear : apple,
    'GET /api/tickets/my-board': () => board(),
    ...extra,
  })
}

const column = (name: string) =>
  within(screen.getByRole('group', { name: 'Spalten von Mein Board' })).getByRole('region', {
    name: new RegExp(`^${name}`),
  })

describe('my board', () => {
  test('my tickets of every space, by category, each card naming its space', async () => {
    myBoardApi()
    await renderApp('/my-board')
    expect(await screen.findByRole('heading', { name: 'Mein Board', level: 1 })).toBeVisible()
    const open = column('Offen')
    expect(within(open).getByRole('link', { name: /HC-42 Login schlägt fehl/ })).toBeVisible()
    expect(within(open).getByText('Projekt Apfel')).toBeInTheDocument()
    expect(within(open).getByText('1 Ticket')).toBeInTheDocument()
    expect(within(column('In Arbeit')).getByText('Projekt Birne')).toBeInTheDocument()
    expect(within(column('Erledigt')).getByText('0 Tickets')).toBeInTheDocument()
    // Moves only where the space allows it: an editor in Apfel, a viewer in Birne.
    expect(screen.getByRole('button', { name: 'HC-42 verschieben' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'HC-7 verschieben' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Spalte von HC-7 ändern' })).toBeNull()
  })

  test('the sidebar leads to it', async () => {
    myBoardApi()
    await renderApp('/tickets')
    const link = await screen.findByRole('link', { name: 'Mein Board' })
    expect(link).toHaveAttribute('href', '/my-board')
  })

  test('a move through the menu sends the category and the version read', async () => {
    let moved = false
    const after = { ...login, status: statusRef(STATUSES[2]!), version: 4 }
    const api = myBoardApi(
      {
        'POST /api/tickets/:number/move-category': () => {
          moved = true
          return makeTicket(after)
        },
      },
      () => (moved ? makeMyBoard(after, report) : makeMyBoard(login, report)),
    )
    const { user } = await renderApp('/my-board')
    await user.click(await screen.findByRole('button', { name: 'Spalte von HC-42 ändern' }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'Zur Prüfung' }))
    await waitFor(() =>
      expect(within(column('Zur Prüfung')).getByRole('link', { name: /HC-42/ })).toBeVisible(),
    )
    expect(api.find('POST', '/api/tickets/42/move-category')[0]!.body).toEqual({
      category: 'review',
      version: 3,
    })
    await waitFor(() =>
      expect(
        within(column('Zur Prüfung')).getByRole('button', { name: 'Spalte von HC-42 ändern' }),
      ).toHaveFocus(),
    )
  })

  test('a space without a status of that category: the card stays and the board says why', async () => {
    myBoardApi({
      'POST /api/tickets/:number/move-category': apiError(422, 'ticket.category_empty'),
    })
    const { user } = await renderApp('/my-board')
    await user.click(await screen.findByRole('button', { name: 'Spalte von HC-42 ändern' }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'Zur Prüfung' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Projekt Apfel hat keinen Status der Kategorie Zur Prüfung',
    )
    expect(within(column('Offen')).getByRole('link', { name: /HC-42/ })).toBeVisible()
    expect(within(column('Zur Prüfung')).queryByRole('link', { name: /HC-42/ })).toBeNull()
  })

  test('changed in the meantime: the card returns and the board says so', async () => {
    myBoardApi({
      'POST /api/tickets/:number/move-category': apiError(409, 'ticket.version_conflict'),
    })
    const { user } = await renderApp('/my-board')
    await user.click(await screen.findByRole('button', { name: 'Spalte von HC-42 ändern' }))
    await user.click(await screen.findByRole('menuitemradio', { name: 'Erledigt' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('inzwischen geändert')
    expect(within(column('Offen')).getByRole('link', { name: /HC-42/ })).toBeVisible()
  })

  test('nothing assigned: says so', async () => {
    myBoardApi({}, () => makeMyBoard())
    await renderApp('/my-board')
    expect(await screen.findByText('Dir ist gerade nichts zugewiesen.')).toBeInTheDocument()
  })
})

describe('my board moves', () => {
  test('a drop on another category is a move; on its own or nothing is none', () => {
    const active = { id: login.id, data: { current: { ticket: login } } }
    expect(categoryDrop({ active, over: { id: 'review' } } as never)).toEqual({
      ticket: login,
      category: 'review',
    })
    expect(categoryDrop({ active, over: { id: 'open' } } as never)).toBeNull()
    expect(categoryDrop({ active, over: null } as never)).toBeNull()
  })

  test('a moved card goes on top of its new column; the counts follow', () => {
    const board = moveMyCard(makeMyBoard(login, report), login, 'active')
    expect(board.columns[0]!.items).toEqual([])
    expect(board.columns[0]!.count).toBe(0)
    expect(board.columns[1]!.items.map((t) => t.number)).toEqual([42, 7])
    expect(board.columns[1]!.items[0]!.status.category).toBe('active')
    expect(board.columns[1]!.count).toBe(2)
  })
})
