import { act, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Message, SpaceRole } from '@/lib/api'
import { makeEntry, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { noteRunProgress } from '@/features/agents/live'
import { HILDA, makeRun } from '@/test/runs'
import { makeTicket, makeTicketSummary, STATUSES, statusRef } from '@/test/tickets'

const hilda = { type: 'agent' as const, id: HILDA.id, name: HILDA.name }

const thread = makeConversation({ kind: 'thread_ticket', name: null, space_id: 'space-1' })

function ticketApi(
  role: SpaceRole,
  messages: Message[],
  extra: object = {},
  ticket = makeTicket(),
) {
  const space = makeSpace({ id: 'space-1', name: 'Projekt Apfel', my_role: role })
  return mockApi({
    ...shellRoutes(makeMe(['directory.read', 'ai.use']), [space]),
    'GET /api/spaces/:id': space,
    'GET /api/tickets/:number': ticket,
    'GET /api/spaces/:id/ticket-statuses': page(STATUSES),
    'GET /api/tickets/:number/thread': thread,
    'GET /api/tickets/:number/pages': page([]),
    'GET /api/conversations/:id/messages': page(
      messages.map((m) => ({ ...m, conversation_id: thread.id })),
    ),
    'POST /api/conversations/:id/read': { status: 204 },
    ...(extra as Record<string, object>),
  })
}

function system(key: string, extra: object = {}) {
  return makeMessage({
    kind: 'system',
    author: null,
    body_md: '',
    system: {
      key,
      actor: { id: HILDA.id, name: HILDA.name, type: 'agent' },
      number: null,
      old: null,
      new: null,
      run_id: 'run-1',
      ...extra,
    },
  })
}

describe('agents on tickets', () => {
  test('a moderator gives the ticket to an agent the API offers', async () => {
    const api = ticketApi('moderator', [], {
      'GET /api/directory': page([makeEntry(hilda)]),
      'PATCH /api/tickets/:number': makeTicket({ version: 2, assignee: hilda }),
    })
    const { user } = await renderApp('/tickets/42')
    const fields = await screen.findByRole('complementary', { name: 'Felder des Tickets' })
    await user.click(within(fields).getByRole('button', { name: 'Jemandem zuweisen' }))
    await user.type(within(fields).getByRole('combobox', { name: 'Zugewiesen an' }), 'Hil')
    await user.click(await screen.findByRole('option', { name: /Hilda/ }))
    await waitFor(() => expect(api.find('PATCH', '/api/tickets/42')).toHaveLength(1))
    expect(api.find('PATCH', '/api/tickets/42')[0]!.body).toEqual({
      assignee: { type: 'agent', id: HILDA.id },
      version: 1,
    })
  })

  test('an agent assignee, its comment, its changes and its stop carry the AI mark', async () => {
    const comment = makeMessage({
      kind: 'agent',
      author: hilda,
      body_md: 'Erledigt bis auf die Freigabe.',
      run_id: 'run-1',
    })
    const status = system('ticket.status_changed', {
      old: { value: STATUSES[1]!.id, name: 'In Arbeit' },
      new: { value: STATUSES[2]!.id, name: 'Zur Prüfung' },
    })
    const handover = system('ticket.assigned', { new: { value: 'bodo', name: 'Bodo' } })
    const refused = system('run.refused', { new: { value: 'run.handover_limit', name: null } })
    const stopped = system('run.stopped', { new: { value: 'max_steps', name: null } })
    ticketApi(
      'viewer',
      [stopped, refused, handover, status, comment],
      { 'GET /api/runs/:id': makeRun({ id: 'run-1' }) },
      makeTicket({
        assignee: hilda,
        status: statusRef(STATUSES[2]!),
      }),
    )
    await renderApp('/tickets/42')
    const fields = await screen.findByRole('complementary', { name: 'Felder des Tickets' })
    const assignee = within(fields).getByText('Hilda').parentElement!
    expect(within(assignee).getByText('Ein KI-Agent')).toBeInTheDocument()

    const discussion = screen.getByRole('complementary', { name: 'Kommentare' })
    const said = await within(discussion).findByRole('article', { name: 'Nachricht von Hilda' })
    expect(within(said).getByText('Von einer KI geschrieben')).toBeInTheDocument()
    const changed = within(discussion)
      .getByText('Hilda hat den Status von In Arbeit auf Zur Prüfung gesetzt.')
      .closest('[data-kind="system"]') as HTMLElement
    expect(within(changed).getByText('Von einer KI geschrieben')).toBeInTheDocument()
    expect(
      within(discussion).getByText('Hilda hat das Ticket an Bodo übergeben.'),
    ).toBeInTheDocument()
    expect(
      within(discussion).getByText(
        'Hilda konnte nicht weitergeben: Die Kette der Übergaben ist zu lang (höchstens 3); der Agent übergibt nicht weiter.',
      ),
    ).toBeInTheDocument()
    const stop = within(discussion)
      .getByText('Der Agent hat die Höchstzahl an Schritten erreicht.')
      .closest('[data-kind="run-stopped"]') as HTMLElement
    expect(within(stop).getByText('Hilda hat ohne Antwort aufgehört:')).toBeInTheDocument()
    // The run is linked for those who may see it (the API showed it).
    expect(await within(stop).findByRole('link', { name: 'Lauf ansehen' })).toHaveAttribute(
      'href',
      '/runs/run-1',
    )
  })

  test('a run that could not start says why, with the agent named', async () => {
    const refused = system('run.refused', { new: { value: 'agent.paused', name: null } })
    ticketApi('viewer', [refused])
    await renderApp('/tickets/42')
    expect(
      await screen.findByText(
        'Hilda konnte nicht beginnen: Dieser Agent ist pausiert und antwortet gerade nicht. Deine Nachricht ist gespeichert.',
      ),
    ).toBeInTheDocument()
  })

  test('board and list cards mark an agent assignee', async () => {
    const summary = makeTicketSummary({ assignee: hilda })
    mockApi({
      ...shellRoutes(makeMe(['directory.read', 'ai.use'])),
      'GET /api/tickets': page([summary]),
      'GET /api/tickets/counts': { assigned_open: 0 },
    })
    await renderApp('/tickets?assignee=me')
    const row = (await screen.findByText('Hilda')).parentElement!
    expect(within(row).getByText('Ein KI-Agent')).toBeInTheDocument()
  })

  test("the ticket's thread shows its run's progress, with a link to the run", async () => {
    ticketApi(
      'viewer',
      [],
      {
        'GET /api/runs/:id': makeRun({
          id: 'run-7',
          state: 'running',
          stop_reason: null,
          steps: 2,
        }),
      },
      makeTicket({ assignee: hilda }),
    )
    const { queryClient } = await renderApp('/tickets/42')
    const discussion = await screen.findByRole('complementary', { name: 'Kommentare' })
    act(() =>
      noteRunProgress(queryClient, {
        type: 'run.progress',
        conversationId: thread.id,
        messageId: null,
        parentId: null,
        ticketId: null,
        spaceId: null,
        runId: 'run-7',
        step: 2,
      }),
    )
    const card = await within(discussion).findByRole('status', { name: 'Hilda arbeitet' })
    // A ticket's run answers in the ticket's thread itself, not in a message's thread.
    expect(within(card).getByText('Hilda arbeitet … (Schritt 3)')).toBeInTheDocument()
    expect(within(card).getByRole('link', { name: 'Lauf ansehen' })).toHaveAttribute(
      'href',
      '/runs/run-7',
    )
  })
})
