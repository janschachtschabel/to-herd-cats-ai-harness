import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Sprint, SpaceRole, TicketSummary } from '@/lib/api'
import { apiError, type Call, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { makeSprint, makeTicket, makeTicketSummary } from '@/test/tickets'

const active = makeSprint({ name: 'Sprint 11', state: 'active', version: 2 })
const planned = makeSprint({ name: 'Sprint 12', state: 'planned', version: 1 })
const closed = makeSprint({
  name: 'Sprint 10',
  state: 'closed',
  tally: { planned: 8, done: 5, carried: 3 },
})

function sprintApi(role: SpaceRole, sprints: Sprint[], extra = {}) {
  const space = makeSpace({ id: 'space-1', name: 'Projekt Apfel', my_role: role })
  return mockApi({
    ...shellRoutes(makeMe(['directory.read']), [space]),
    'GET /api/spaces/:id': space,
    'GET /api/spaces/:id/pages/tree': page([]),
    'GET /api/spaces/:id/sprints': (call: Call) => {
      const states = call.query.getAll('state')
      return page(states.length ? sprints.filter((s) => states.includes(s.state)) : sprints)
    },
    'GET /api/tickets': page([]),
    ...extra,
  })
}

const sprintItem = (name: string) => screen.getByRole('article', { name: new RegExp(`^${name}`) })

describe('sprints', () => {
  test('a viewer reads the sprints and a closed sprint’s tally, and may change nothing', async () => {
    sprintApi('viewer', [active, planned, closed])
    await renderApp('/spaces/space-1/sprints')
    expect(await screen.findByRole('article', { name: /^Sprint 11/ })).toHaveTextContent('Aktiv')
    expect(sprintItem('Sprint 12')).toHaveTextContent('Geplant')
    expect(sprintItem('Sprint 10')).toHaveTextContent('8 geplant · 5 erledigt · 3 übertragen')
    expect(screen.queryByRole('button', { name: 'Neuer Sprint' })).toBeNull()
    expect(screen.queryByRole('button', { name: /starten/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /abschließen/ })).toBeNull()
    const views = screen.getByRole('navigation', { name: 'Ansichten des Bereichs' })
    expect(within(views).getByRole('link', { name: 'Sprints' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(views).getByRole('link', { name: 'Vorrat' })).toBeInTheDocument()
  })

  test('an editor puts tickets in sprints but manages none (ticket.assign)', async () => {
    sprintApi('editor', [planned])
    await renderApp('/spaces/space-1/sprints')
    await screen.findByRole('article', { name: /^Sprint 12/ })
    expect(screen.queryByRole('button', { name: 'Neuer Sprint' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Sprint 12 starten' })).toBeNull()
  })

  test('a moderator creates a sprint', async () => {
    const api = sprintApi('moderator', [], {
      'POST /api/spaces/:id/sprints': { status: 201, body: planned },
    })
    const { user } = await renderApp('/spaces/space-1/sprints')
    expect(await screen.findByText('Noch keine Sprints in diesem Bereich.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Neuer Sprint' }))
    const dialog = await screen.findByRole('dialog', { name: 'Neuer Sprint' })
    await user.type(within(dialog).getByLabelText('Name'), 'Sprint 12')
    await user.type(within(dialog).getByLabelText('Ziel'), 'Anmeldung stabil')
    await user.type(within(dialog).getByLabelText('Beginn'), '2026-11-16')
    await user.type(within(dialog).getByLabelText('Ende'), '2026-11-27')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(api.find('POST', '/api/spaces/space-1/sprints')).toHaveLength(1))
    expect(api.find('POST', '/api/spaces/space-1/sprints')[0]!.body).toEqual({
      name: 'Sprint 12',
      goal: 'Anmeldung stabil',
      starts_on: '2026-11-16',
      ends_on: '2026-11-27',
    })
  })

  test('a planned sprint starts with the version read; one running already says so', async () => {
    const api = sprintApi('moderator', [planned], {
      'POST /api/sprints/:id/start': apiError(409, 'sprint.active_exists'),
    })
    const { user } = await renderApp('/spaces/space-1/sprints')
    await user.click(await screen.findByRole('button', { name: 'Sprint 12 starten' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'In diesem Bereich läuft schon ein Sprint',
    )
    expect(api.find('POST', `/api/sprints/${planned.id}/start`)[0]!.body).toEqual({ version: 1 })
  })

  test('while a sprint runs, starting another is not offered', async () => {
    sprintApi('moderator', [active, planned])
    await renderApp('/spaces/space-1/sprints')
    await screen.findByRole('article', { name: /^Sprint 12/ })
    expect(screen.queryByRole('button', { name: 'Sprint 12 starten' })).toBeNull()
    expect(sprintItem('Sprint 12')).toHaveTextContent(
      'Starten geht, sobald Sprint 11 abgeschlossen ist.',
    )
  })

  test('closing asks where the unfinished tickets go, then shows the tally', async () => {
    let done = false
    const finished = {
      ...active,
      state: 'closed' as const,
      tally: { planned: 4, done: 3, carried: 1 },
    }
    const api = sprintApi('moderator', [active, planned], {
      'POST /api/sprints/:id/close': () => {
        done = true
        return finished
      },
      'GET /api/spaces/:id/sprints': () => page(done ? [planned, finished] : [active, planned]),
    })
    const { user } = await renderApp('/spaces/space-1/sprints')
    await user.click(await screen.findByRole('button', { name: 'Sprint 11 abschließen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Sprint 11 abschließen' })
    const next = within(dialog).getByRole('radio', { name: /In den nächsten Sprint: Sprint 12/ })
    expect(next).toBeChecked()
    await user.click(within(dialog).getByRole('radio', { name: 'Zurück in den Vorrat' }))
    await user.click(within(dialog).getByRole('button', { name: 'Abschließen' }))
    await waitFor(() => expect(api.find('POST', `/api/sprints/${active.id}/close`)).toHaveLength(1))
    expect(api.find('POST', `/api/sprints/${active.id}/close`)[0]!.body).toEqual({
      version: 2,
      move_open_to: 'backlog',
    })
    expect(await screen.findByText('4 geplant · 3 erledigt · 1 übertragen')).toBeInTheDocument()
  })

  test('without a planned sprint the unfinished tickets can only go to the backlog', async () => {
    sprintApi('moderator', [active])
    const { user } = await renderApp('/spaces/space-1/sprints')
    await user.click(await screen.findByRole('button', { name: 'Sprint 11 abschließen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Sprint 11 abschließen' })
    expect(within(dialog).getByRole('radio', { name: /In den nächsten Sprint/ })).toBeDisabled()
    expect(within(dialog).getByRole('radio', { name: 'Zurück in den Vorrat' })).toBeChecked()
  })

  test('a closed sprint shows its tickets; a reopened one is marked, not hidden', async () => {
    const reopened = makeTicketSummary({ number: 7, title: 'Wieder offen', sprint_id: closed.id })
    const api = sprintApi('viewer', [closed], {
      'GET /api/tickets': (call: Call) =>
        page(call.query.get('sprint') === closed.id ? [reopened] : []),
    })
    const { user } = await renderApp('/spaces/space-1/sprints')
    await user.click(await screen.findByRole('button', { name: 'Tickets von Sprint 10 zeigen' }))
    const item = sprintItem('Sprint 10')
    expect(await within(item).findByRole('link', { name: /HC-7 Wieder offen/ })).toBeVisible()
    expect(within(item).getByText('Wieder offen nach dem Abschluss')).toBeInTheDocument()
    expect(api.find('GET', '/api/tickets').at(-1)!.query.get('space_id')).toBe('space-1')
  })
})

describe('backlog', () => {
  const first = makeTicketSummary({ number: 42, version: 3, priority: 'high' })
  const second = makeTicketSummary({ number: 43, title: 'Export bricht ab', version: 5 })

  function backlogApi(role: SpaceRole, tickets: TicketSummary[], extra = {}) {
    return sprintApi(role, [active, planned], {
      'GET /api/tickets': (call: Call) => page(call.query.get('sprint') === 'none' ? tickets : []),
      ...extra,
    })
  }

  test('lists the unfinished tickets without a sprint, by priority', async () => {
    const api = backlogApi('viewer', [first, second])
    await renderApp('/spaces/space-1/backlog')
    expect(await screen.findByRole('link', { name: /HC-42/ })).toBeVisible()
    const asked = api.find('GET', '/api/tickets').at(-1)!.query
    expect(asked.get('space_id')).toBe('space-1')
    expect(asked.get('sprint')).toBe('none')
    expect(asked.get('sort')).toBe('priority')
    expect(asked.getAll('status_category')).toEqual(['open', 'active', 'review'])
    // A viewer plans nothing.
    expect(screen.queryByRole('checkbox')).toBeNull()
    expect(screen.queryByRole('button', { name: /In Sprint legen/ })).toBeNull()
  })

  test('an editor picks tickets by keyboard and puts them into a sprint, each with its version', async () => {
    let moved = false
    const api = backlogApi('editor', [first, second], {
      'PATCH /api/tickets/:number': (call: Call) => {
        moved = true
        return makeTicket({ number: Number(call.path.split('/').at(-1)), sprint_id: planned.id })
      },
      'GET /api/tickets': (call: Call) =>
        page(call.query.get('sprint') === 'none' && !moved ? [first, second] : []),
    })
    const { user } = await renderApp('/spaces/space-1/backlog')
    const pick = await screen.findByRole('checkbox', { name: 'HC-42 auswählen' })
    pick.focus()
    await user.keyboard(' ')
    await user.tab() // the ticket's link
    await user.tab()
    expect(screen.getByRole('checkbox', { name: 'HC-43 auswählen' })).toHaveFocus()
    await user.keyboard(' ')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Ziel-Sprint' }), 'Sprint 12')
    await user.click(screen.getByRole('button', { name: 'In Sprint legen (2)' }))
    await waitFor(() => expect(api.find('PATCH', '/api/tickets/43')).toHaveLength(1))
    expect(api.find('PATCH', '/api/tickets/42')[0]!.body).toEqual({
      sprint_id: planned.id,
      version: 3,
    })
    expect(api.find('PATCH', '/api/tickets/43')[0]!.body).toEqual({
      sprint_id: planned.id,
      version: 5,
    })
    expect(await screen.findByText('2 Tickets in Sprint 12 gelegt.')).toHaveAttribute(
      'role',
      'status',
    )
  })

  test('a ticket changed in the meantime stays and the backlog says so', async () => {
    backlogApi('editor', [first], {
      'PATCH /api/tickets/:number': apiError(409, 'ticket.version_conflict'),
    })
    const { user } = await renderApp('/spaces/space-1/backlog')
    await user.click(await screen.findByRole('checkbox', { name: 'Alle auswählen' }))
    await user.click(screen.getByRole('button', { name: 'In Sprint legen (1)' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '1 Ticket wurde inzwischen geändert und blieb im Vorrat',
    )
  })
})
