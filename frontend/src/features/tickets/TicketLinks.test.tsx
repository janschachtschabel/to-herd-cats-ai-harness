import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, test } from 'vitest'
import { clearPending } from '@/features/messaging/conversation/pending'
import type { Epic, SpaceRole, TicketHit, TicketSummary } from '@/lib/api'
import { apiError, type Call, makeMe, makePage, makeSpace, mockApi, nodeOf, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { makeTicket, makeTicketSummary, STATUSES, statusRef } from '@/test/tickets'

afterEach(() => clearPending())

const me = makeMe(['directory.read'])

describe('ticket cards in messages', () => {
  test('a named ticket one may see shows as a card; a hidden or free one stays text', async () => {
    const space = makeSpace({ id: 'space-1', name: 'Projekt Apfel', my_role: 'viewer' })
    const channel = makeConversation()
    const message = makeMessage({
      conversation_id: channel.id,
      body_md: 'Siehe HC-42 und HC-7, nicht `HC-9`.',
    })
    const api = mockApi({
      ...shellRoutes(me, [space]),
      'GET /api/conversations/:id': channel,
      'GET /api/conversations/:id/messages': page([message]),
      'POST /api/conversations/:id/read': { status: 204 },
      'GET /api/tickets/:number': (_call: Call, { number }: Record<string, string>) =>
        number === '42' ? makeTicket() : apiError(404, 'ticket.not_found'),
    })
    await renderApp(`/c/${channel.id}`)
    const card = await screen.findByRole('link', { name: 'Ticket HC-42: Login schlägt fehl' })
    expect(card).toHaveAttribute('href', '/tickets/42')
    expect(within(card).getByText('Neu')).toBeInTheDocument()
    await waitFor(() => expect(api.find('GET', '/api/tickets/7')).toHaveLength(1))
    expect(screen.queryByRole('link', { name: /^Ticket HC-7/ })).toBeNull()
    // The message still reads as written; a key in code names no ticket.
    expect(screen.getByText(/Siehe HC-42 und HC-7/)).toBeInTheDocument()
    expect(api.find('GET', '/api/tickets/9')).toHaveLength(0)
  })
})

describe('epics', () => {
  test('an epic shows its progress and opens its children', async () => {
    const space = makeSpace({ id: 'space-1', name: 'Projekt Apfel', my_role: 'viewer' })
    const epic: Epic = {
      ...makeTicketSummary({ number: 10, kind: 'epic', title: 'Neue Anmeldung' }),
      children: { open: 1, active: 1, review: 0, done: 2, cancelled: 0 },
    }
    const child = makeTicketSummary({
      number: 11,
      title: 'Passwort vergessen',
      status: statusRef(STATUSES[3]!),
      parent: { id: epic.id, number: 10, key: 'HC-10', title: epic.title, kind: 'epic' },
    })
    const api = mockApi({
      ...shellRoutes(me, [space]),
      'GET /api/spaces/:id': space,
      'GET /api/spaces/:id/pages/tree': page([]),
      'GET /api/tags': page([]),
      'GET /api/spaces/:id/epics': page([epic]),
      'GET /api/tickets': page([child]),
    })
    const { user } = await renderApp('/spaces/space-1/epics')
    expect(await screen.findByRole('link', { name: 'HC-10 Neue Anmeldung' })).toBeVisible()
    expect(screen.getByRole('img', { name: '2 von 4 erledigt' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Neues Epic' })).toBeNull()
    const toggle = screen.getByRole('button', { name: 'Untergeordnete Tickets von HC-10 zeigen' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(await screen.findByRole('link', { name: 'HC-11 Passwort vergessen' })).toBeVisible()
    expect(api.find('GET', '/api/tickets')[0]!.query.get('parent')).toBe(epic.id)
  })
})

describe('tickets on a wiki page', () => {
  function pageApi(role: SpaceRole, linked: TicketSummary[], extra = {}) {
    const space = makeSpace({ id: 'space-1', name: 'Handbuch', my_role: role })
    const urlaub = makePage({ space_id: space.id, title: 'Urlaub', path: 'urlaub' })
    const api = mockApi({
      ...shellRoutes(me, [space]),
      'GET /api/spaces/:id': space,
      'GET /api/spaces/:id/pages/tree': page([nodeOf(urlaub)]),
      'GET /api/spaces/:id/pages/by-path': urlaub,
      'GET /api/tags': page([]),
      'GET /api/pages/:id/attachments': page([]),
      'GET /api/pages/:id/tickets': () => page(linked),
      ...extra,
    })
    return { api, urlaub }
  }

  test('a reader sees the linked tickets and cannot change them', async () => {
    pageApi('viewer', [makeTicketSummary()])
    await renderApp('/spaces/space-1/p/urlaub')
    const section = await screen.findByRole('region', { name: 'Verknüpfte Tickets' })
    expect(
      await within(section).findByRole('link', { name: 'HC-42 Login schlägt fehl' }),
    ).toBeVisible()
    expect(within(section).queryByRole('button')).toBeNull()
  })

  test('an editor links a ticket found by its key and unlinks it again', async () => {
    const linked: TicketSummary[] = []
    const hit: TicketHit = {
      type: 'ticket',
      id: 't42',
      number: 42,
      key: 'HC-42',
      title: 'Login schlägt fehl',
      kind: 'task',
      status: statusRef(STATUSES[0]!),
      space_id: 'space-1',
      space_name: 'Handbuch',
      snippet: '',
      score: 1,
    }
    const { api, urlaub } = pageApi('editor', linked, {
      'GET /api/search': page([hit]),
      'PUT /api/tickets/:number/pages/:pageId': () => {
        linked.push(makeTicketSummary())
        return { status: 204 }
      },
      'DELETE /api/tickets/:number/pages/:pageId': () => {
        linked.pop()
        return { status: 204 }
      },
    })
    const { user } = await renderApp('/spaces/space-1/p/urlaub')
    const section = await screen.findByRole('region', { name: 'Verknüpfte Tickets' })
    expect(
      await within(section).findByText('Noch keine Tickets mit dieser Seite verknüpft.'),
    ).toBeInTheDocument()
    await user.click(within(section).getByRole('button', { name: 'Ticket verknüpfen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Ticket verknüpfen' })
    await user.type(within(dialog).getByRole('combobox', { name: 'Suchen' }), 'HC-42')
    await within(dialog).findByRole('option', { name: /HC-42/ })
    await user.keyboard('{Enter}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(api.find('PUT', `/api/tickets/42/pages/${urlaub.id}`)).toHaveLength(1)
    expect(api.find('GET', '/api/search')[0]!.query.get('types')).toBe('ticket')
    await user.click(
      await within(section).findByRole('button', { name: 'Verknüpfung mit HC-42 lösen' }),
    )
    expect(
      await within(section).findByText('Noch keine Tickets mit dieser Seite verknüpft.'),
    ).toBeInTheDocument()
    expect(api.find('DELETE', `/api/tickets/42/pages/${urlaub.id}`)).toHaveLength(1)
  })

  test('a refused link says why inside the picker', async () => {
    const hit = {
      type: 'ticket',
      id: 't42',
      number: 42,
      key: 'HC-42',
      title: 'Login schlägt fehl',
      kind: 'task',
      status: statusRef(STATUSES[0]!),
      space_id: 'space-2',
      space_name: 'Fremd',
      snippet: '',
      score: 1,
    }
    pageApi('editor', [], {
      'GET /api/search': page([hit]),
      'PUT /api/tickets/:number/pages/:pageId': apiError(403, 'auth.forbidden'),
    })
    const { user } = await renderApp('/spaces/space-1/p/urlaub')
    await user.click(await screen.findByRole('button', { name: 'Ticket verknüpfen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Ticket verknüpfen' })
    await user.type(within(dialog).getByRole('combobox', { name: 'Suchen' }), 'HC-42')
    await user.click(await within(dialog).findByRole('option', { name: /HC-42/ }))
    expect(await within(dialog).findByRole('alert')).toBeInTheDocument()
  })
})
