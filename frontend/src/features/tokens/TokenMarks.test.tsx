import { screen, within } from '@testing-library/react'
import { afterEach, describe, expect, test } from 'vitest'
import { clearPending } from '@/features/messaging/conversation/pending'
import {
  type Call,
  makeMe,
  makePage,
  makeSpace,
  makeVersion,
  mockApi,
  nodeOf,
  page,
} from '@/test/api'
import { makeConversation, makeMessage, shellRoutes } from '@/test/messaging'
import { makeProposal } from '@/test/proposals'
import { renderApp } from '@/test/render'
import { makeTicket, makeTicketSummary, STATUSES } from '@/test/tickets'

afterEach(() => clearPending())

const space = makeSpace({ id: 'space-1', name: 'Werkstatt', my_role: 'editor' })
const codi = { type: 'agent' as const, id: '00000000-0000-7000-8000-0000000000e1', name: 'Codi' }
const thread = makeConversation({ kind: 'thread_ticket', name: null, space_id: space.id })

function ticketApi(
  messages: ReturnType<typeof makeMessage>[],
  ticket = makeTicket(),
  permissions = ['directory.read'],
) {
  return mockApi({
    ...shellRoutes(makeMe(permissions), [space]),
    'GET /api/spaces/:id': space,
    'GET /api/tickets/:number': ticket,
    'GET /api/spaces/:id/ticket-statuses': page(STATUSES),
    'GET /api/tickets/:number/thread': thread,
    'GET /api/tickets/:number/pages': page([]),
    'GET /api/conversations/:id/messages': (call: Call) =>
      page(
        call.query.get('include_system') === 'false'
          ? messages.filter((m) => m.kind !== 'system')
          : messages,
      ),
    'POST /api/conversations/:id/read': { status: 204 },
  })
}

describe('what a token wrote, and tickets waiting for an external agent', () => {
  test('a ticket given to an external agent waits for pick-up, in the view and the list', async () => {
    ticketApi([], makeTicket({ assignee: codi, awaiting_pickup: true }))
    const { router } = await renderApp('/tickets/42')
    const fields = await screen.findByRole('complementary', { name: 'Felder des Tickets' })
    expect(within(fields).getByText('Wartet auf Abholung')).toBeInTheDocument()

    mockApi({
      ...shellRoutes(makeMe([]), [space]),
      'GET /api/tickets/counts': { assigned_open: 1 },
      'GET /api/tickets': page([
        makeTicketSummary({ title: 'Abholen', number: 7, assignee: codi, awaiting_pickup: true }),
        makeTicketSummary({ title: 'Läuft', number: 8, assignee: codi }),
      ]),
    })
    await router.navigate({ to: '/tickets' })
    const waiting = (await screen.findByRole('link', { name: /HC-7/ })).closest('li')!
    expect(within(waiting).getByText('Wartet auf Abholung')).toBeInTheDocument()
    const working = screen.getByRole('link', { name: /HC-8/ }).closest('li')!
    expect(within(working).queryByText('Wartet auf Abholung')).not.toBeInTheDocument()
  })

  test("the ticket thread marks a token's comment and timeline entry with the AI mark and its name", async () => {
    const comment = makeMessage({
      conversation_id: thread.id,
      author: { type: 'user', id: 'lea', name: 'Lea Löwe' },
      body_md: 'Erledigt bis auf die Tests.',
      via_token: 'Claude Code Laptop',
    })
    const entry = makeMessage({
      conversation_id: thread.id,
      kind: 'system',
      author: null,
      body_md: '{}',
      via_token: 'Pipeline',
      system: {
        key: 'ticket.status_changed',
        actor: { id: codi.id, name: 'Codi', type: 'agent' },
        number: null,
        old: { value: STATUSES[0]!.id, name: 'Neu' },
        new: { value: STATUSES[1]!.id, name: 'In Arbeit' },
      },
    })
    ticketApi([comment, entry], makeTicket({ via_token: 'Claude Code Laptop' }))
    await renderApp('/tickets/42')
    const article = await screen.findByRole('article', { name: 'Nachricht von Lea Löwe' })
    expect(within(article).getByText('Von einer KI geschrieben')).toBeInTheDocument()
    expect(within(article).getByText('über Token „Claude Code Laptop“')).toBeInTheDocument()
    const line = screen.getByText(/hat den Status/).closest('[data-kind="system"]') as HTMLElement
    expect(within(line).getByText('über Token „Pipeline“')).toBeInTheDocument()
    expect(within(line).getAllByText('Von einer KI geschrieben')).toHaveLength(1)
    const crumbs = screen.getByRole('navigation', { name: 'Wo das Ticket steht' })
    expect(within(crumbs).getByText('über Token „Claude Code Laptop“')).toBeInTheDocument()
  })

  test("an external agent's comment through its token offers no run sources", async () => {
    const comment = makeMessage({
      conversation_id: thread.id,
      kind: 'agent',
      author: codi,
      body_md: 'Übernommen.',
      client_id: '00000000-0000-7000-8000-0000000000c1',
      via_token: 'Pipeline',
    })
    ticketApi([comment], makeTicket(), ['directory.read', 'ai.use'])
    await renderApp('/tickets/42')
    const article = await screen.findByRole('article', { name: 'Nachricht von Codi' })
    expect(within(article).getByText('über Token „Pipeline“')).toBeInTheDocument()
    expect(within(article).queryByText('Quellen anzeigen')).not.toBeInTheDocument()
  })

  test('proposals and page versions written through a token say so; source mcp has a label', async () => {
    const doc = makePage({ id: 'page-1', space_id: space.id, title: 'Handbuch', path: 'handbuch' })
    const proposal = makeProposal({
      space_id: space.id,
      page_id: doc.id,
      author: { type: 'user', id: 'lea', name: 'Lea Löwe' },
      ai: true,
      via_token: 'Laptop',
    })
    const api = {
      'GET /api/auth/me': makeMe(['ai.use']),
      'GET /api/spaces': page([{ ...space, my_role: 'moderator' as const }]),
      'GET /api/spaces/:id': { ...space, my_role: 'moderator' as const },
      'GET /api/spaces/:id/pages/tree': page([nodeOf(doc)]),
      'GET /api/spaces/:id/pages/by-path': doc,
      'GET /api/spaces/:id/proposals': page([proposal]),
      'GET /api/pages/:id/attachments': page([]),
      'GET /api/pages/:id/tickets': page([]),
      'GET /api/pages/:id/versions': page([
        makeVersion(2, {
          source: 'mcp',
          ai: true,
          via_token: 'Laptop',
          author: { type: 'user', id: 'lea', name: 'Lea Löwe' },
        }),
        makeVersion(1),
      ]),
      'GET /api/pages/:id/diff': {
        from_number: 1,
        to_number: 2,
        from_title: 'Handbuch',
        to_title: 'Handbuch',
        title_changed: false,
        hunks: [],
      },
    }
    mockApi(api)
    const { router } = await renderApp(`/spaces/${space.id}/proposals`)
    const item = (await screen.findByRole('link', { name: /Änderung an/ })).closest('li')!
    expect(within(item).getByText('Von einer KI geschrieben')).toBeInTheDocument()
    expect(within(item).getByText('über Token „Laptop“')).toBeInTheDocument()

    await router.navigate({ to: `/spaces/${space.id}/p/handbuch`, search: { view: 'versions' } })
    const rows = await screen.findAllByRole('row')
    const row = rows.find((r) => within(r).queryByText('Version 2'))!
    expect(within(row).getByText('Über MCP')).toBeInTheDocument()
    expect(within(row).getByText('über Token „Laptop“')).toBeInTheDocument()
  })
})
