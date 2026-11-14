import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Message, Permission } from '@/lib/api'
import { apiError, makeMe, makeSpace, mockApi, page, type Call } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { HILDA, makeApproval, makeEvent, makeQuestion, makeRun } from '@/test/runs'

const PAGE = '00000000-0000-7000-8000-000000000a01'
const hilda = { type: 'agent' as const, id: HILDA.id, name: HILDA.name }

function card(type: 'approval' | 'question', id: string, body: string): Message {
  return makeMessage({
    kind: type,
    author: hilda,
    body_md: body,
    run_id: 'run-1',
    card: { type, id },
  })
}

/** A channel with one card message; `me` is the person asked unless said otherwise. */
function channelWith(message: Message, routes: object, meId = 'asker', extra: Permission[] = []) {
  const me = makeMe(['directory.read', 'ai.use', ...extra], { id: meId })
  const space = makeSpace({ id: 'space-1', name: 'Handbuch', my_role: 'editor' })
  const channel = makeConversation({ space_id: space.id })
  const api = mockApi({
    ...shellRoutes(me, [space]),
    'GET /api/spaces/:id': space,
    'GET /api/conversations/:id': channel,
    'GET /api/conversations/:id/messages': page([{ ...message, conversation_id: channel.id }]),
    'POST /api/conversations/:id/read': { status: 204 },
    'GET /api/runs/:id': makeRun({ id: 'run-1', state: 'waiting', stop_reason: null }),
    ...(routes as Record<string, object>),
  })
  return { api, channel }
}

describe('a release card', () => {
  test('the person asked reads what the agent wants, its diff, and releases it', async () => {
    const pending = makeApproval({
      id: 'ap-1',
      args: { page_id: PAGE, content_md: 'Neu', reason: 'Neue Frist' },
      summary: `propose_page_change: page_id=${PAGE}`,
    })
    const { api, channel } = channelWith(card('approval', 'ap-1', pending.summary), {
      'GET /api/approvals/:id': pending,
      'GET /api/approvals/:id/diff': [
        { kind: 'delete', lines: ['Alt'] },
        { kind: 'insert', lines: ['Neu'] },
      ],
      'POST /api/approvals/:id/decide': makeApproval({
        ...pending,
        state: 'approved',
        decided_by: 'asker',
        decided_at: '2026-11-14T10:00:00Z',
        version: 2,
      }),
    })
    const { user } = await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Freigabe' })
    expect(
      within(shown).getByText('Freigabe erbeten: Änderung an einer Seite vorschlagen'),
    ).toBeInTheDocument()
    expect(within(shown).getByText(`propose_page_change: page_id=${PAGE}`)).toBeInTheDocument()
    expect(within(shown).getByText('Wartet auf Entscheidung')).toBeInTheDocument()
    expect(within(shown).getByText(/Du entscheidest\./)).toBeInTheDocument()
    expect(within(shown).getByRole('link', { name: 'Betroffene Seite öffnen' })).toHaveAttribute(
      'href',
      `/go/page/${PAGE}`,
    )
    expect(within(shown).getByRole('link', { name: 'Lauf ansehen' })).toHaveAttribute(
      'href',
      '/runs/run-1',
    )
    // The card's message carries the AI mark.
    const message = screen.getByRole('article', { name: 'Nachricht von Hilda' })
    expect(within(message).getByText('Von einer KI geschrieben')).toBeInTheDocument()

    await user.click(within(shown).getByRole('button', { name: 'Änderung ansehen' }))
    expect(await within(shown).findByText('Neu')).toBeInTheDocument()
    // The page's full text is the diff; the other arguments stay readable, folded.
    await user.click(within(shown).getByText('Angaben des Aufrufs'))
    expect(within(shown).getByText(/Neue Frist/)).toBeInTheDocument()

    await user.click(within(shown).getByRole('button', { name: 'Freigeben' }))
    await waitFor(() => expect(api.find('POST', '/api/approvals/ap-1/decide')).toHaveLength(1))
    expect(api.find('POST', '/api/approvals/ap-1/decide')[0]!.body).toEqual({
      decision: 'approve',
      version: 1,
    })
    expect(await within(shown).findByText('Freigegeben')).toBeInTheDocument()
    expect(within(shown).queryByRole('button', { name: 'Freigeben' })).toBeNull()
  })

  test('a rejection takes an optional reason and shows it', async () => {
    const pending = makeApproval({ id: 'ap-2', tool: 'comment_ticket', diff_url: null })
    const { api, channel } = channelWith(card('approval', 'ap-2', pending.summary), {
      'GET /api/approvals/:id': pending,
      'POST /api/approvals/:id/decide': (call: Call) =>
        makeApproval({
          ...pending,
          state: 'rejected',
          reason: (call.body as { reason: string }).reason,
          decided_at: '2026-11-14T10:00:00Z',
          version: 2,
        }),
    })
    const { user } = await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Freigabe' })
    await user.click(within(shown).getByRole('button', { name: 'Ablehnen' }))
    await user.type(
      within(shown).getByLabelText('Begründung (freiwillig, geht an den Agenten)'),
      'Zu früh',
    )
    await user.click(within(shown).getByRole('button', { name: 'Ablehnen' }))
    await waitFor(() => expect(api.find('POST', '/api/approvals/ap-2/decide')).toHaveLength(1))
    expect(api.find('POST', '/api/approvals/ap-2/decide')[0]!.body).toEqual({
      decision: 'reject',
      reason: 'Zu früh',
      version: 1,
    })
    expect(await within(shown).findByText('Abgelehnt')).toBeInTheDocument()
    expect(within(shown).getByText('Begründung: Zu früh')).toBeInTheDocument()
  })

  test('a decision that comes too late is put into words, and the card shows what happened', async () => {
    const pending = makeApproval({ id: 'ap-3' })
    let decided = false
    const { channel } = channelWith(card('approval', 'ap-3', pending.summary), {
      'GET /api/approvals/:id': () =>
        decided ? makeApproval({ ...pending, state: 'expired', version: 2 }) : pending,
      'POST /api/approvals/:id/decide': () => {
        decided = true
        return apiError(409, 'approval.expired')
      },
    })
    const { user } = await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Freigabe' })
    await user.click(within(shown).getByRole('button', { name: 'Freigeben' }))
    expect(
      await within(shown).findByText(
        'Diese Freigabe ist abgelaufen; der Agent hat aufgehört zu warten.',
      ),
    ).toBeInTheDocument()
    expect(await within(shown).findByText('Abgelaufen')).toBeInTheDocument()
    expect(within(shown).queryByRole('button', { name: 'Freigeben' })).toBeNull()
  })

  test('an approved call that found its object changed is shown as stale', async () => {
    const approved = makeApproval({
      id: 'ap-4',
      state: 'approved',
      step: 2,
      call_id: 'call_0',
      decided_at: '2026-11-14T10:00:00Z',
      version: 2,
    })
    const { channel } = channelWith(card('approval', 'ap-4', approved.summary), {
      'GET /api/approvals/:id': approved,
      'GET /api/runs/:id/events': page([
        makeEvent({
          kind: 'tool_call',
          content: {
            step: 2,
            call_id: 'call_0',
            name: 'propose_page_change',
            source: 'approval',
            text: 'approval_stale: what this call would change has changed',
          },
        }),
      ]),
    })
    await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Freigabe' })
    expect(await within(shown).findByText('Veraltet')).toBeInTheDocument()
    expect(
      within(shown).getByText(/Der Inhalt hat sich seit der Anfrage geändert/),
    ).toBeInTheDocument()
  })

  test('someone else who sees the run sees the card without actions, and who decides', async () => {
    const pending = makeApproval({ id: 'ap-5', args: null, diff_url: null })
    const { channel } = channelWith(
      card('approval', 'ap-5', pending.summary),
      { 'GET /api/approvals/:id': pending },
      'responsible',
    )
    await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Freigabe' })
    expect(await within(shown).findByText(/Entscheiden kann Jan Jansen\./)).toBeInTheDocument()
    expect(within(shown).queryByRole('button')).toBeNull()
  })

  test('a reader the API does not show the card sees its summary only', async () => {
    const { channel } = channelWith(card('approval', 'ap-6', 'update_page: page_id=x'), {
      'GET /api/approvals/:id': apiError(404, 'approval.not_found'),
    })
    await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Freigabe' })
    expect(within(shown).getByText('update_page: page_id=x')).toBeInTheDocument()
    expect(
      await within(shown).findByText(
        /Entscheiden kann nur die Person, die den Agenten gefragt hat/,
      ),
    ).toBeInTheDocument()
    expect(within(shown).queryByRole('button')).toBeNull()
  })
})

describe('a question card', () => {
  test('the person asked answers; the answer stands on the card', async () => {
    const asked = makeQuestion({ id: 'q-1', question: 'Für welches Jahr?' })
    const { api, channel } = channelWith(card('question', 'q-1', asked.question), {
      'GET /api/questions/:id': asked,
      'POST /api/questions/:id/answer': (call: Call) =>
        makeQuestion({
          ...asked,
          state: 'answered',
          answer: (call.body as { text: string }).text,
          answered_at: '2026-11-14T10:00:00Z',
          version: 2,
        }),
    })
    const { user } = await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Rückfrage' })
    expect(within(shown).getByText('Für welches Jahr?')).toBeInTheDocument()
    await user.type(within(shown).getByLabelText('Deine Antwort'), '2027')
    await user.click(within(shown).getByRole('button', { name: 'Antworten' }))
    await waitFor(() => expect(api.find('POST', '/api/questions/q-1/answer')).toHaveLength(1))
    expect(api.find('POST', '/api/questions/q-1/answer')[0]!.body).toEqual({
      text: '2027',
      version: 1,
    })
    expect(await within(shown).findByText('Beantwortet')).toBeInTheDocument()
    expect(within(shown).getByText('Deine Antwort: 2027')).toBeInTheDocument()
  })

  test('an answer to a run that ended is put into words', async () => {
    const asked = makeQuestion({ id: 'q-2' })
    const { channel } = channelWith(card('question', 'q-2', asked.question), {
      'GET /api/questions/:id': asked,
      'POST /api/questions/:id/answer': apiError(409, 'question.run_ended'),
    })
    const { user } = await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Rückfrage' })
    await user.type(within(shown).getByLabelText('Deine Antwort'), 'ja')
    await user.click(within(shown).getByRole('button', { name: 'Antworten' }))
    expect(
      await within(shown).findByText(
        'Der Lauf wartet nicht mehr auf die Antwort (er ist beendet oder wurde abgebrochen).',
      ),
    ).toBeInTheDocument()
  })

  test('someone else reads the question without the answer field', async () => {
    const asked = makeQuestion({ id: 'q-3' })
    const { channel } = channelWith(
      card('question', 'q-3', asked.question),
      { 'GET /api/questions/:id': asked },
      'responsible',
    )
    await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Rückfrage' })
    expect(
      await within(shown).findByText('Antworten kann die Person, die den Agenten gefragt hat.'),
    ).toBeInTheDocument()
    expect(within(shown).queryByRole('textbox')).toBeNull()
  })
})

describe('my releases', () => {
  test('the sidebar counts them; the list shows each card with where it was asked', async () => {
    const one = makeApproval({ id: 'ap-7', run_id: 'run-7' })
    const me = makeMe(['directory.read', 'ai.use'], { id: 'asker' })
    const api = mockApi({
      ...shellRoutes(me),
      'GET /api/approvals': (call: Call) =>
        page(
          call.query.get('state') === 'pending'
            ? [one]
            : [one, makeApproval({ state: 'rejected' })],
        ),
      'GET /api/runs/:id': makeRun({ id: 'run-7', state: 'waiting', stop_reason: null }),
    })
    const { user } = await renderApp('/approvals')
    const nav = await screen.findByRole('link', { name: /Freigaben/ })
    expect(await within(nav).findByText('1 Freigabe wartet')).toBeInTheDocument()
    const list = await screen.findByRole('list', { name: 'Freigaben' })
    expect(within(list).getAllByRole('region', { name: 'Freigabe' })).toHaveLength(1)
    expect(await within(list).findByRole('link', { name: 'HC-7' })).toHaveAttribute(
      'href',
      '/tickets/7',
    )
    await user.selectOptions(screen.getByLabelText('Zustand'), 'Alle')
    await waitFor(() =>
      expect(
        within(screen.getByRole('list', { name: 'Freigaben' })).getAllByRole('region'),
      ).toHaveLength(2),
    )
    expect(api.find('GET', '/api/approvals').some((c) => c.query.get('state') === null)).toBe(true)
  })

  test('nothing waiting reads as such', async () => {
    mockApi({ ...shellRoutes(makeMe(['ai.use'])) })
    await renderApp('/approvals')
    expect(await screen.findByText('Keine offenen Freigaben.')).toBeInTheDocument()
  })

  test("a run's page shows the release card at its waiting call", async () => {
    const one = makeApproval({ id: 'ap-8', run_id: 'run-8', step: 1, call_id: 'c1' })
    mockApi({
      ...shellRoutes(makeMe(['ai.use'], { id: 'asker' })),
      'GET /api/approvals': page([one]),
      'GET /api/runs/:id': makeRun({ id: 'run-8', state: 'waiting', stop_reason: null }),
      'GET /api/runs/:id/events': page([
        makeEvent({
          kind: 'model_call',
          content: { step: 1, tool_calls: [{ id: 'c1', name: 'propose_page_change', args: {} }] },
        }),
      ]),
    })
    await renderApp('/runs/run-8')
    const steps = await screen.findByRole('list', { name: 'Schritte des Laufs' })
    const shown = await within(steps).findByRole('region', { name: 'Freigabe' })
    expect(within(shown).getByRole('button', { name: 'Freigeben' })).toBeInTheDocument()
  })
})
