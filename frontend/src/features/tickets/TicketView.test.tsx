import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, test } from 'vitest'
import { clearPending } from '@/features/messaging/conversation/pending'
import type { SpaceRole, Ticket } from '@/lib/api'
import { apiError, type Call, makeEntry, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { makeSprint, makeTicket, STATUSES, statusRef } from '@/test/tickets'

afterEach(() => clearPending())

const thread = makeConversation({ kind: 'thread_ticket', name: null, space_id: 'space-1' })

function system(key: string, extra: object = {}) {
  return makeMessage({
    conversation_id: thread.id,
    kind: 'system',
    author: null,
    body_md: '{}',
    system: {
      key,
      actor: { id: 'jan', name: 'Jan Jansen' },
      number: null,
      old: null,
      new: null,
      ...extra,
    },
  })
}

function ticketApi(role: SpaceRole, ticket: Ticket = makeTicket(), extra = {}) {
  const space = makeSpace({ id: 'space-1', name: 'Projekt Apfel', my_role: role })
  const changed = system('ticket.status_changed', {
    old: { value: STATUSES[0]!.id, name: 'Neu' },
    new: { value: STATUSES[1]!.id, name: 'In Arbeit' },
  })
  const due = system('ticket.due_changed', { new: { value: '2026-11-20', name: null } })
  const comment = makeMessage({ conversation_id: thread.id, body_md: 'Ich schaue es mir an.' })
  return mockApi({
    ...shellRoutes(makeMe(['directory.read']), [space]),
    'GET /api/spaces/:id': space,
    'GET /api/tickets/:number': ticket,
    'GET /api/spaces/:id/ticket-statuses': page(STATUSES),
    'GET /api/tickets/:number/thread': thread,
    'GET /api/tickets/:number/pages': page([]),
    'GET /api/conversations/:id/messages': (call: Call) =>
      page(call.query.get('include_system') === 'false' ? [comment] : [comment, due, changed]),
    'POST /api/conversations/:id/read': { status: 204 },
    ...extra,
  })
}

describe('ticket view', () => {
  test('a viewer reads the fields and the worded timeline, and may change nothing', async () => {
    ticketApi('viewer')
    await renderApp('/tickets/42')
    expect(await screen.findByRole('heading', { name: 'Login schlägt fehl' })).toBeInTheDocument()
    expect(screen.getByText('Anmelden', { selector: 'strong' })).toBeInTheDocument()
    const fields = screen.getByRole('complementary', { name: 'Felder des Tickets' })
    expect(within(fields).getByText('Neu')).toBeInTheDocument()
    expect(within(fields).queryByRole('combobox')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Übernehmen' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Titel ändern' })).toBeNull()
    const discussion = screen.getByRole('complementary', { name: 'Kommentare' })
    expect(
      await within(discussion).findByText(
        'Jan Jansen hat den Status von Neu auf In Arbeit gesetzt.',
      ),
    ).toBeInTheDocument()
    expect(
      within(discussion).getByText('Jan Jansen hat die Fälligkeit auf 20.11.2026 gesetzt.'),
    ).toBeInTheDocument()
  })

  test('system entries can be hidden; comments stay', async () => {
    const api = ticketApi('viewer')
    const { user } = await renderApp('/tickets/42')
    const discussion = await screen.findByRole('complementary', { name: 'Kommentare' })
    await within(discussion).findByText('Ich schaue es mir an.')
    await user.click(
      within(discussion).getByRole('checkbox', { name: 'Systemmeldungen ausblenden' }),
    )
    await waitFor(() => expect(within(discussion).queryByText(/hat den Status von Neu/)).toBeNull())
    expect(within(discussion).getByText('Ich schaue es mir an.')).toBeInTheDocument()
    const asked = api.find('GET', `/api/conversations/${thread.id}/messages`)
    expect(asked.at(-1)!.query.get('include_system')).toBe('false')
  })

  test('an editor changes the status and takes the ticket, each with the version read', async () => {
    let current = makeTicket({ version: 3 })
    const api = ticketApi('editor', current, {
      'PATCH /api/tickets/:number': (call: Call) => {
        const body = call.body as { status_id?: string; assignee?: { id: string } }
        current = {
          ...current,
          version: current.version + 1,
          ...(body.status_id ? { status: statusRef(STATUSES[1]!) } : {}),
          ...(body.assignee
            ? { assignee: { type: 'user', id: body.assignee.id, name: 'Mia Muster' } }
            : {}),
        }
        return current
      },
      'GET /api/tickets/:number': () => current,
    })
    const { user } = await renderApp('/tickets/42')
    const fields = await screen.findByRole('complementary', { name: 'Felder des Tickets' })
    await user.selectOptions(
      await within(fields).findByRole('combobox', { name: 'Status' }),
      'In Arbeit',
    )
    await waitFor(() => expect(api.find('PATCH', '/api/tickets/42')).toHaveLength(1))
    expect(api.find('PATCH', '/api/tickets/42')[0]!.body).toEqual({
      status_id: STATUSES[1]!.id,
      version: 3,
    })
    await user.click(within(fields).getByRole('button', { name: 'Übernehmen' }))
    await waitFor(() => expect(api.find('PATCH', '/api/tickets/42')).toHaveLength(2))
    const take = api.find('PATCH', '/api/tickets/42')[1]!.body as {
      version: number
      assignee: object
    }
    expect(take.version).toBe(4)
    expect(take.assignee).toMatchObject({ type: 'user' })
    expect(await within(fields).findByText('Mia Muster')).toBeInTheDocument()
    // Assigning others needs ticket.assign (moderator): not offered to an editor.
    expect(within(fields).queryByRole('button', { name: 'Jemandem zuweisen' })).toBeNull()
  })

  test('a moderator assigns someone who may read the space', async () => {
    const lea = makeEntry({ name: 'Lea Löwe' })
    const api = ticketApi('moderator', makeTicket(), {
      'GET /api/directory': page([lea]),
      'PATCH /api/tickets/:number': makeTicket({ version: 2 }),
    })
    const { user } = await renderApp('/tickets/42')
    const fields = await screen.findByRole('complementary', { name: 'Felder des Tickets' })
    await user.click(within(fields).getByRole('button', { name: 'Jemandem zuweisen' }))
    await user.type(within(fields).getByRole('combobox', { name: 'Zugewiesen an' }), 'Lea')
    await user.click(await screen.findByRole('option', { name: /Lea Löwe/ }))
    await waitFor(() => expect(api.find('PATCH', '/api/tickets/42')).toHaveLength(1))
    expect(api.find('PATCH', '/api/tickets/42')[0]!.body).toEqual({
      assignee: { type: 'user', id: lea.id },
      version: 1,
    })
    expect(api.find('GET', '/api/directory').at(-1)!.query.get('space_id')).toBe('space-1')
  })

  test('changed in the meantime: says so, reloads, and keeps what was typed', async () => {
    let version = 1
    const id = '00000000-0000-7000-b000-0000000000aa'
    const api = ticketApi('editor', makeTicket(), {
      'GET /api/tickets/:number': () => makeTicket({ id, version }),
      'PATCH /api/tickets/:number': (call: Call) =>
        (call.body as { version: number }).version === 2
          ? makeTicket({ id, title: 'Anmeldung klemmt', version: 3 })
          : apiError(409, 'ticket.version_conflict'),
    })
    const { user } = await renderApp('/tickets/42')
    await user.click(await screen.findByRole('button', { name: 'Titel ändern' }))
    const input = screen.getByRole('textbox', { name: 'Titel' })
    await user.clear(input)
    await user.type(input, 'Anmeldung klemmt')
    await user.click(screen.getByRole('button', { name: 'Speichern' }))
    expect(await screen.findByText(/inzwischen geändert/)).toBeInTheDocument()
    version = 2
    await user.click(screen.getByRole('button', { name: 'Aktuelle Fassung laden' }))
    await waitFor(() => expect(screen.queryByText(/inzwischen geändert/)).toBeNull())
    expect(screen.getByRole('textbox', { name: 'Titel' })).toHaveValue('Anmeldung klemmt')
    await user.click(screen.getByRole('button', { name: 'Speichern' }))
    expect(await screen.findByRole('heading', { name: 'Anmeldung klemmt' })).toBeInTheDocument()
    expect(
      api.find('PATCH', '/api/tickets/42').map((c) => (c.body as { version: number }).version),
    ).toEqual([1, 2])
  })

  test('a text edit saves against the version it was opened at, not a later live one', async () => {
    let version = 1
    const id = '00000000-0000-7000-b000-0000000000ab'
    const api = ticketApi('editor', makeTicket(), {
      'GET /api/tickets/:number': () =>
        makeTicket({ id, version, description_md: version > 1 ? 'Von Jan geändert.' : 'Alt.' }),
      'PATCH /api/tickets/:number': () => apiError(409, 'ticket.version_conflict'),
    })
    const { user, queryClient } = await renderApp('/tickets/42')
    await user.click(await screen.findByRole('button', { name: 'Bearbeiten' }))
    const field = screen.getByRole('textbox', { name: 'Beschreibung' })
    await user.clear(field)
    await user.type(field, 'Meine Fassung.')
    // Someone else saves meanwhile; the live event refreshes the ticket under the form.
    version = 2
    await queryClient.invalidateQueries({ queryKey: ['tickets'] })
    await waitFor(() => expect(api.find('GET', '/api/tickets/42').length).toBeGreaterThanOrEqual(2))
    await user.click(screen.getByRole('button', { name: 'Speichern' }))
    expect(await screen.findByText(/inzwischen geändert/)).toBeInTheDocument()
    expect(field).toHaveValue('Meine Fassung.')
    expect((api.find('PATCH', '/api/tickets/42')[0]!.body as { version: number }).version).toBe(1)
  })

  test('an editor puts the ticket in a sprint and back into the backlog', async () => {
    const running = makeSprint({ name: 'Sprint 11', state: 'active' })
    const next = makeSprint({ name: 'Sprint 12', state: 'planned' })
    let current = makeTicket({ version: 2 })
    const api = ticketApi('editor', current, {
      'GET /api/spaces/:id/sprints': page([running, next]),
      'GET /api/tickets/:number': () => current,
      'PATCH /api/tickets/:number': (call: Call) => {
        const body = call.body as { sprint_id: string | null }
        current = { ...current, sprint_id: body.sprint_id, version: current.version + 1 }
        return current
      },
    })
    const { user } = await renderApp('/tickets/42')
    const fields = await screen.findByRole('complementary', { name: 'Felder des Tickets' })
    const field = await within(fields).findByRole('combobox', { name: 'Sprint' })
    expect(field).toHaveValue('')
    await user.selectOptions(field, 'Sprint 12')
    await waitFor(() => expect(api.find('PATCH', '/api/tickets/42')).toHaveLength(1))
    expect(api.find('PATCH', '/api/tickets/42')[0]!.body).toEqual({
      sprint_id: next.id,
      version: 2,
    })
    await waitFor(() => expect(field).toHaveValue(next.id))
    await user.selectOptions(field, 'Kein Sprint (Vorrat)')
    await waitFor(() => expect(api.find('PATCH', '/api/tickets/42')).toHaveLength(2))
    expect(api.find('PATCH', '/api/tickets/42')[1]!.body).toEqual({ sprint_id: null, version: 3 })
  })

  test('a ticket in a closed sprint names it, without a hint to move it', async () => {
    const closed = makeSprint({
      name: 'Sprint 10',
      state: 'closed',
      tally: { planned: 3, done: 3, carried: 0 },
    })
    ticketApi('viewer', makeTicket({ sprint_id: closed.id }), {
      'GET /api/spaces/:id/sprints': page([closed]),
    })
    await renderApp('/tickets/42')
    const fields = await screen.findByRole('complementary', { name: 'Felder des Tickets' })
    expect(await within(fields).findByText('Sprint 10 (abgeschlossen)')).toBeInTheDocument()
    expect(within(fields).queryByText(/Der Sprint ist abgeschlossen/)).not.toBeInTheDocument()
  })

  test('a ticket one may not see is not there, as a free number', async () => {
    ticketApi('viewer', makeTicket(), {
      'GET /api/tickets/:number': apiError(404, 'ticket.not_found'),
    })
    await renderApp('/tickets/7')
    expect(
      await screen.findByText('Dieses Ticket gibt es nicht, oder du darfst es nicht sehen.'),
    ).toBeInTheDocument()
  })
})
