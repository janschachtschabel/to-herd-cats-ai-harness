import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Board, BoardRow, SpaceRole, TicketSummary } from '@/lib/api'
import { type Call, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { makeSprint, makeTicketSummary, STATUSES, statusRef } from '@/test/tickets'

const LEA = { type: 'user' as const, id: '00000000-0000-7000-c000-000000000001', name: 'Lea Löwe' }
const BEN = { type: 'user' as const, id: '00000000-0000-7000-c000-000000000002', name: 'Ben Berg' }
const sprint = makeSprint({ name: 'Sprint 11', state: 'active' })
const planned = makeSprint({ name: 'Sprint 12', state: 'planned' })

const login = makeTicketSummary({ number: 42, assignee: LEA })
const report = makeTicketSummary({
  number: 43,
  title: 'Bericht schreiben',
  assignee: LEA,
  status: statusRef(STATUSES[1]!),
})
const loose = makeTicketSummary({ number: 44, title: 'Ohne Person' })

type Card = TicketSummary & { changed: boolean }

function row(assignee: BoardRow['assignee'], cards: Card[]): BoardRow {
  return {
    assignee,
    cells: STATUSES.map((status) => {
      const items = cards.filter((card) => card.status.id === status.id)
      return {
        status_id: status.id,
        count: items.length,
        changed: items.filter((card) => card.changed).length,
        items,
        next_cursor: null,
      }
    }),
  }
}

function daily(rows: BoardRow[]): Board {
  return {
    columns: STATUSES.map((status) => ({
      status: statusRef(status),
      count: rows.reduce(
        (sum, r) => sum + r.cells.find((c) => c.status_id === status.id)!.count,
        0,
      ),
      items: [],
      next_cursor: null,
    })),
    rows,
    changed_since: '2026-11-13T00:00:00Z',
    rows_truncated: false,
  }
}

const ALL_ROWS = [
  row(BEN, []),
  row(LEA, [
    { ...login, changed: false },
    { ...report, changed: true },
  ]),
  row(null, [{ ...loose, changed: false }]),
]

function dailyApi(role: SpaceRole, extra = {}) {
  const space = makeSpace({ id: 'space-1', name: 'Projekt Apfel', my_role: role })
  return mockApi({
    ...shellRoutes(makeMe(['directory.read']), [space]),
    'GET /api/spaces/:id': space,
    'GET /api/spaces/:id/pages/tree': page([]),
    'GET /api/tags': page([]),
    'GET /api/spaces/:id/epics': page([]),
    'GET /api/spaces/:id/sprints': page([sprint, planned]),
    'GET /api/spaces/:id/board': (call: Call) => {
      if (call.query.get('group_by') !== 'assignee') return { columns: [] }
      const who = call.query.get('assignee')
      if (who === LEA.id) return daily([ALL_ROWS[1]!])
      return daily(ALL_ROWS)
    },
    ...extra,
  })
}

const personRow = (name: string) => screen.getByRole('region', { name: new RegExp(`^${name}`) })

describe('daily view', () => {
  test('grouped by person: the active sprint first, a row per person with counts', async () => {
    const api = dailyApi('viewer')
    const { user } = await renderApp('/spaces/space-1/board')
    await user.click(await screen.findByRole('checkbox', { name: 'Nach Person gruppieren' }))
    expect(await screen.findByRole('region', { name: /^Lea Löwe/ })).toBeVisible()
    const asked = api.find('GET', '/api/spaces/space-1/board').at(-1)!.query
    expect(asked.get('group_by')).toBe('assignee')
    expect(asked.get('sprint')).toBe(sprint.id)
    expect(screen.getByRole('combobox', { name: 'Sprint' })).toHaveValue(sprint.id)

    const lea = personRow('Lea Löwe')
    expect(within(lea).getByText('2 Tickets, 1 seit dem letzten Arbeitstag geändert')).toBeVisible()
    const working = within(lea).getByRole('group', { name: 'Lea Löwe: In Arbeit' })
    expect(within(working).getByRole('article', { name: /^HC-43/ })).toHaveTextContent('Geändert')
    expect(within(lea).getByRole('article', { name: /^HC-42/ })).not.toHaveTextContent('Geändert')
    expect(
      within(personRow('Nicht zugewiesen')).getByRole('article', { name: /^HC-44/ }),
    ).toBeVisible()
    expect(screen.getByText(/Hervorgehoben ist, was seit Freitag, 13\.11\./)).toBeInTheDocument()
  })

  test('a click on a person filters to them; the filter can be lifted', async () => {
    const api = dailyApi('viewer')
    const { user } = await renderApp('/spaces/space-1/board')
    await user.click(await screen.findByRole('checkbox', { name: 'Nach Person gruppieren' }))
    await user.click(await screen.findByRole('button', { name: 'Nur Lea Löwe zeigen' }))
    await waitFor(() => expect(screen.queryByRole('region', { name: /^Ben Berg/ })).toBeNull())
    expect(api.find('GET', '/api/spaces/space-1/board').at(-1)!.query.get('assignee')).toBe(LEA.id)
    await user.click(screen.getByRole('button', { name: 'Alle Personen zeigen' }))
    expect(await screen.findByRole('region', { name: /^Ben Berg/ })).toBeVisible()
  })

  test('the sprint can be changed, to the backlog too, in either mode', async () => {
    const api = dailyApi('viewer')
    const { user } = await renderApp('/spaces/space-1/board')
    const choice = await screen.findByRole('combobox', { name: 'Sprint' })
    await user.selectOptions(choice, 'Vorrat (ohne Sprint)')
    await waitFor(() =>
      expect(api.find('GET', '/api/spaces/space-1/board').at(-1)!.query.get('sprint')).toBe('none'),
    )
  })

  test('the daily mode, the sprint and the person stand in the address', async () => {
    // Module review M4b, finding 9: a reload or a shared link keeps the view.
    dailyApi('viewer')
    const { user, router } = await renderApp('/spaces/space-1/board')
    await user.click(await screen.findByRole('checkbox', { name: 'Nach Person gruppieren' }))
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Sprint' }), planned.id)
    await user.click(await screen.findByRole('button', { name: 'Nur Lea Löwe zeigen' }))
    await waitFor(() =>
      expect(router.state.location.search).toEqual({
        group: 'assignee',
        sprint: planned.id,
        assignee: LEA.id,
      }),
    )
    await user.click(screen.getByRole('checkbox', { name: 'Nach Person gruppieren' }))
    await waitFor(() => expect(router.state.location.search).toEqual({ sprint: planned.id }))
  })

  test('opened from a link, the board starts in the daily mode it names', async () => {
    const api = dailyApi('viewer')
    await renderApp(`/spaces/space-1/board?group=assignee&sprint=${planned.id}&kind=nonsense`)
    expect(await screen.findByRole('region', { name: /^Lea Löwe/ })).toBeVisible()
    expect(screen.getByRole('checkbox', { name: 'Nach Person gruppieren' })).toBeChecked()
    const asked = api.find('GET', '/api/spaces/space-1/board').at(-1)!.query
    expect(asked.get('group_by')).toBe('assignee')
    expect(asked.get('sprint')).toBe(planned.id)
    expect(asked.get('kind')).toBeNull() // not a kind: left out
  })
})
