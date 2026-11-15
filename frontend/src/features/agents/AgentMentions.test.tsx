import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, test } from 'vitest'
import { clearPending } from '@/features/messaging/conversation/pending'
import type { Message, Permission } from '@/lib/api'
import { type Call, makeEntry, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes, written } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { HILDA, makeRun } from '@/test/runs'

afterEach(() => clearPending())

const hilda = { type: 'agent' as const, id: HILDA.id, name: HILDA.name }

function channelApi(permissions: Permission[], messages: Message[], extra: object = {}) {
  const me = makeMe(['directory.read', ...permissions])
  const space = makeSpace({ id: 'space-1', name: 'Handbuch', my_role: 'editor' })
  const channel = makeConversation({ space_id: space.id })
  const api = mockApi({
    ...shellRoutes(me, [space]),
    'GET /api/spaces/:id': space,
    'GET /api/conversations/:id': channel,
    'GET /api/conversations/:id/messages': page(
      messages.map((m) => ({ ...m, conversation_id: channel.id })),
    ),
    'POST /api/conversations/:id/read': { status: 204 },
    ...(extra as Record<string, object>),
  })
  return { api, channel, me }
}

describe('mentioning an agent', () => {
  test('the picker offers the agents the API offers for the place, with the AI mark', async () => {
    const lea = makeEntry({ name: 'Lea Löwe' })
    const hildaEntry = makeEntry(hilda)
    let sent: Message | null = null
    const { api, channel } = channelApi(['ai.use'], [], {
      'GET /api/directory': page([hildaEntry, lea]),
      'POST /api/conversations/:id/messages': (call: Call) => {
        const body = call.body as { body_md: string; client_id: string }
        sent = makeMessage({ body_md: body.body_md, client_id: body.client_id })
        return { ...written(sent), agent_run: { id: 'run-1', reason: null, agent_id: HILDA.id } }
      },
      'GET /api/runs/:id': makeRun({ state: 'running', stop_reason: null, steps: 1 }),
      'GET /api/messages/:id': () => sent,
      'GET /api/messages/:id/replies': page([]),
    })
    const { user } = await renderApp(`/c/${channel.id}`)
    const box = await screen.findByRole('combobox', { name: 'Nachricht an #allgemein' })
    await user.type(box, '@hi')
    const option = await screen.findByRole('option', { name: /Hilda/ })
    expect(within(option).getByText('Ein KI-Agent')).toBeInTheDocument()
    // People and member agents together: no type filter, the space decides.
    const asked = api.find('GET', '/api/directory').at(-1)!
    expect(asked.query.get('space_id')).toBe('space-1')
    expect(asked.query.get('type')).toBeNull()
    await user.click(option)
    expect(box).toHaveValue(`@[Hilda](agent:${HILDA.id}) `)
    await user.type(box, 'was steht an?{Enter}')
    await waitFor(() =>
      expect(api.find('POST', `/api/conversations/${channel.id}/messages`)).toHaveLength(1),
    )
    const body = api.find('POST', `/api/conversations/${channel.id}/messages`)[0]!.body as {
      mentions: string[]
    }
    expect(body.mentions).toEqual([HILDA.id])
    // Its run works in the thread of the message: the card says so and links the run.
    const card = await screen.findByRole('status', { name: 'Hilda arbeitet' })
    expect(within(card).getByText(/im Thread/)).toBeInTheDocument()
    expect(within(card).getByRole('link', { name: 'Lauf ansehen' })).toHaveAttribute(
      'href',
      '/runs/run-1',
    )
    // The thread where it answers shows the card as well.
    await user.click(within(card).getByRole('button', { name: 'Thread öffnen' }))
    const panel = await screen.findByRole('complementary', { name: 'Thread' })
    expect(await within(panel).findByRole('status', { name: 'Hilda arbeitet' })).toBeInTheDocument()
  })

  test('without AI, no agent is offered (the API offers none) and none is asked', async () => {
    const { api, channel } = channelApi([], [], {
      'GET /api/directory': page([makeEntry({ name: 'Lea Löwe' })]),
    })
    const { user } = await renderApp(`/c/${channel.id}`)
    await user.type(await screen.findByRole('combobox', { name: 'Nachricht an #allgemein' }), '@h')
    await screen.findByRole('option', { name: /Lea Löwe/ })
    expect(screen.queryByRole('option', { name: /Hilda/ })).toBeNull()
    expect(api.find('GET', '/api/directory').length).toBeGreaterThan(0)
  })

  test('a refusal is put into words under the composer', async () => {
    const { channel } = channelApi(['ai.use'], [], {
      'GET /api/directory': page([makeEntry(hilda)]),
      'POST /api/conversations/:id/messages': (call: Call) => {
        const body = call.body as { body_md: string; client_id: string }
        const sent = makeMessage({ body_md: body.body_md, client_id: body.client_id })
        return {
          ...written(sent),
          agent_run: { id: null, reason: 'run.waiting', agent_id: HILDA.id },
        }
      },
    })
    const { user } = await renderApp(`/c/${channel.id}`)
    const box = await screen.findByRole('combobox', { name: 'Nachricht an #allgemein' })
    await user.type(box, '@hi')
    await user.click(await screen.findByRole('option', { name: /Hilda/ }))
    await user.type(box, 'bitte{Enter}')
    expect(await screen.findByText(/arbeitet hier schon an einem Auftrag/)).toBeInTheDocument()
  })

  test('an agent mention reads as a name, never as a link', async () => {
    const { channel } = channelApi(
      ['ai.use'],
      [makeMessage({ body_md: `Frag @[Hilda](agent:${HILDA.id}) bitte` })],
    )
    await renderApp(`/c/${channel.id}`)
    const name = await screen.findByText('@Hilda')
    expect(name.tagName).toBe('SPAN')
    expect(name).toHaveClass('mention')
  })
})
