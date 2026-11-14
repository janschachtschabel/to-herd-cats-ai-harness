import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, test } from 'vitest'
import { clearPending } from '@/features/messaging/conversation/pending'
import type { Message, Permission } from '@/lib/api'
import { makeEntry, makeMe, makePage, makeSpace, mockApi, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes, written } from '@/test/messaging'
import { renderApp } from '@/test/render'

afterEach(() => clearPending())

const AGENT = { id: '00000000-0000-7000-8000-0000000000a1', name: 'Hilda' }
const RUN = '00000000-0000-7000-8000-0000000000r1'.replace('r', 'e')

function dmApi(
  permissions: Permission[],
  messages: Message[],
  extra: Record<string, unknown> = {},
) {
  const me = makeMe(['directory.read', ...permissions])
  const dm = makeConversation({
    kind: 'dm',
    space_id: null,
    name: null,
    participants: [
      { id: me.user.id, name: me.user.name, is_active: true, type: 'user' },
      { id: AGENT.id, name: AGENT.name, is_active: true, type: 'agent' },
    ],
  })
  const api = mockApi({
    ...shellRoutes(me),
    'GET /api/conversations/:id': dm,
    'GET /api/conversations/:id/messages': page(
      messages.map((m) => ({ ...m, conversation_id: dm.id })),
    ),
    'POST /api/conversations/:id/read': { status: 204 },
    'GET /api/agents/:id/profile': {
      id: AGENT.id,
      name: AGENT.name,
      intro: 'Ich beantworte Fragen zum Handbuch.',
      status: 'active',
    },
    ...(extra as Record<string, object>),
  })
  return { api, dm, me }
}

const agentAnswer = (body: string) =>
  makeMessage({
    kind: 'agent',
    author: { type: 'agent', id: AGENT.id, name: AGENT.name },
    body_md: body,
    client_id: RUN,
  })

describe('a direct message with an agent', () => {
  test('the answer carries the AI mark and its sources; a stopped run says why', async () => {
    const handbook = makePage({ title: 'Urlaubsregeln', path: 'urlaub' })
    const stopped = makeMessage({
      kind: 'system',
      author: null,
      body_md: '',
      system: {
        key: 'run.stopped',
        actor: null,
        number: null,
        old: null,
        new: { value: 'policy_blocked', name: null },
      },
      created_at: '2026-11-13T09:05:00Z',
    })
    const { dm } = dmApi(['ai.use'], [stopped, agentAnswer('Es gibt 30 Tage Urlaub.')], {
      'GET /api/runs/:id/events': page([
        {
          id: 'e1',
          attempt: 1,
          seq: 2,
          kind: 'tool_call',
          content: {
            name: 'read_page',
            source: 'wiki',
            attrs: { id: handbook.id },
            text: '# Urlaub',
          },
          redacted: false,
          created_at: '2026-11-13T09:00:00Z',
        },
      ]),
      'GET /api/pages/:id': handbook,
    })
    const { user } = await renderApp(`/c/${dm.id}`)
    const answer = await screen.findByRole('article', { name: 'Nachricht von Hilda' })
    expect(within(answer).getByText('Von einer KI geschrieben')).toBeInTheDocument()
    expect(within(answer).getByText('Es gibt 30 Tage Urlaub.')).toBeInTheDocument()
    expect(within(answer).queryByRole('button', { name: 'Nachricht bearbeiten' })).toBeNull()
    expect(screen.getByText(/Ich beantworte Fragen zum Handbuch/)).toBeInTheDocument()
    expect(screen.getByText(/Durch die KI-Richtlinie eines Bereichs gestoppt/)).toBeInTheDocument()

    await user.click(within(answer).getByRole('button', { name: 'Quellen anzeigen' }))
    expect(await within(answer).findByRole('link', { name: 'Urlaubsregeln' })).toHaveAttribute(
      'href',
      `/spaces/${handbook.space_id}/p/urlaub`,
    )
  })

  test('a source the reader may not see is named as such, not linked', async () => {
    const { dm } = dmApi(['ai.use'], [agentAnswer('Siehe Handbuch.')], {
      'GET /api/runs/:id/events': page([
        {
          id: 'e1',
          attempt: 1,
          seq: 2,
          kind: 'tool_call',
          content: { step: 1, call_id: 'c1', name: 'read_page', source: 'wiki' },
          redacted: true,
          created_at: '2026-11-13T09:00:00Z',
        },
      ]),
    })
    const { user } = await renderApp(`/c/${dm.id}`)
    const answer = await screen.findByRole('article', { name: 'Nachricht von Hilda' })
    await user.click(within(answer).getByRole('button', { name: 'Quellen anzeigen' }))
    expect(
      await within(answer).findByText('1 Quelle ist für dich nicht sichtbar.'),
    ).toBeInTheDocument()
    expect(within(answer).queryByRole('link')).toBeNull()
    expect(within(answer).queryByText('Keine Quellen gelesen.')).toBeNull()
  })

  test('sending to a paused agent says that it will not answer now', async () => {
    let sent: Message | null = null
    const { dm } = dmApi(['ai.use'], [], {
      'POST /api/conversations/:id/messages': (call: {
        body: { body_md: string; client_id: string }
      }) => {
        sent = makeMessage({ body_md: call.body.body_md, client_id: call.body.client_id })
        return { ...written(sent), agent_run: { id: null, reason: 'agent.paused' } }
      },
    })
    const { user } = await renderApp(`/c/${dm.id}`)
    const box = await screen.findByRole('combobox', { name: 'Nachricht an Direktnachricht' })
    await user.type(box, 'Hallo Hilda{Enter}')
    expect(
      await screen.findByText(/Dieser Agent ist pausiert und antwortet gerade nicht/),
    ).toBeInTheDocument()
    expect(sent).not.toBeNull()
  })

  test('after sending, a card follows the run until its answer', async () => {
    const run = {
      id: RUN,
      agent_id: AGENT.id,
      conversation_id: 'x',
      trigger_message_id: 'm',
      state: 'running',
      stop_reason: null,
      attempt: 1,
      steps: 2,
      created_at: '2026-11-13T09:00:00Z',
      started_at: '2026-11-13T09:00:01Z',
      finished_at: null,
    }
    const { dm, api } = dmApi(['ai.use'], [], {
      'POST /api/conversations/:id/messages': (call: { body: { body_md: string } }) => ({
        ...written(makeMessage({ body_md: call.body.body_md })),
        agent_run: { id: RUN, reason: null },
      }),
      'GET /api/runs/:id': run,
    })
    const { user } = await renderApp(`/c/${dm.id}`)
    const box = await screen.findByRole('combobox', { name: 'Nachricht an Direktnachricht' })
    await user.type(box, 'Wie viele Urlaubstage?{Enter}')
    expect(await screen.findByText('Hilda arbeitet … (Schritt 3)')).toBeInTheDocument()
    expect(api.find('GET', `/api/runs/${RUN}`)).toHaveLength(1)
  })

  test('the DM dialog offers agents only with ai.use', async () => {
    const hilda = makeEntry({ type: 'agent', id: AGENT.id, name: AGENT.name })
    const me = makeMe(['directory.read', 'ai.use'])
    const api = mockApi({
      ...shellRoutes(me, [makeSpace()]),
      'GET /api/directory': (call) => page(call.query.get('type') === 'agent' ? [hilda] : []),
      'POST /api/dms': makeConversation({ kind: 'dm', id: '00000000-0000-7000-8000-0000000000d1' }),
      'GET /api/conversations/:id': makeConversation({ kind: 'dm' }),
      'GET /api/conversations/:id/messages': page([]),
      'POST /api/conversations/:id/read': { status: 204 },
    })
    const { user } = await renderApp('/spaces')
    await user.click(await screen.findByRole('button', { name: 'Direktnachricht beginnen' }))
    const dialog = await screen.findByRole('dialog')
    const picker = within(dialog).getByRole('combobox', { name: 'Agent' })
    await user.click(picker)
    await user.click(await within(dialog).findByRole('option', { name: /Hilda/ }))
    await user.click(within(dialog).getByRole('button', { name: 'Gespräch öffnen' }))
    await waitFor(() =>
      expect(api.find('POST', '/api/dms')[0]?.body).toEqual({ agent_id: AGENT.id }),
    )
  })

  test('without ai.use the DM dialog has no agents and never asks for them', async () => {
    const me = makeMe(['directory.read'])
    const api = mockApi({
      ...shellRoutes(me, [makeSpace()]),
      'GET /api/directory': page([]),
    })
    const { user } = await renderApp('/spaces')
    await user.click(await screen.findByRole('button', { name: 'Direktnachricht beginnen' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).queryByText('Mit einem Agenten sprechen')).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole('combobox'))
    await waitFor(() => expect(api.find('GET', '/api/directory').length).toBeGreaterThan(0))
    expect(api.find('GET', '/api/directory').map((c) => c.query.get('type'))).not.toContain('agent')
  })
})
