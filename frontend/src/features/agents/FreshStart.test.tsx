import { screen, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Conversation, Message } from '@/lib/api'
import { makeMe, mockApi, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'

const AGENT = { id: '00000000-0000-7000-8000-0000000000a1', name: 'Hilda' }
const BOB = { id: '00000000-0000-7000-8000-0000000000b0', name: 'Bob Berg' }

function open(conversation: Partial<Conversation>, messages: Message[] = []) {
  const me = makeMe(['directory.read', 'ai.use'])
  const dm = makeConversation({
    kind: 'dm',
    space_id: null,
    name: null,
    version: 4,
    participants: [
      { id: me.user.id, name: me.user.name, is_active: true, type: 'user' },
      { id: AGENT.id, name: AGENT.name, is_active: true, type: 'agent' },
    ],
    ...conversation,
  })
  const api = mockApi({
    ...shellRoutes(me),
    'GET /api/conversations/:id': dm,
    'GET /api/conversations/:id/messages': page(
      messages.map((m) => ({ ...m, conversation_id: dm.id })),
    ),
    'POST /api/conversations/:id/read': { status: 204 },
    'POST /api/conversations/:id/fresh-start': {
      ...dm,
      version: 5,
      fresh_start_at: '2026-11-13T10:00:00Z',
    },
    'GET /api/agents/:id/profile': { id: AGENT.id, name: AGENT.name, intro: '', status: 'active' },
    'GET /api/runs/:id/events': page([]),
  })
  return { dm, api, me }
}

const said = (body: string, at: string, personal = false) =>
  makeMessage({
    kind: 'agent',
    author: { type: 'agent', id: AGENT.id, name: AGENT.name },
    body_md: body,
    personal,
    created_at: at,
  })

describe('"Neu beginnen" in her DM alone with an agent (module review M8 3, H2)', () => {
  test('explains itself, asks first, and sends the version it read', async () => {
    const { dm, api } = open({})
    const { user } = await renderApp(`/c/${dm.id}`)
    await user.click(await screen.findByRole('button', { name: 'Neu beginnen' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent(/bekommt Hilda in diesem Gespräch nichts mehr von dem, was davor war/)
    expect(dialog).toHaveTextContent(/Suche in seinen früheren Läufen/)
    expect(dialog).toHaveTextContent(/zum Merken freigegeben hast, bleibt/)
    expect(dialog).toHaveTextContent(/Markierung „Persönlich“ endet/)
    expect(api.find('POST', `/api/conversations/${dm.id}/fresh-start`)).toHaveLength(0)
    await user.click(within(dialog).getByRole('button', { name: 'Neu beginnen' }))
    await screen.findByText(/Neu begonnen/)
    const [sent] = api.find('POST', `/api/conversations/${dm.id}/fresh-start`)
    expect(sent!.body).toEqual({ version: 4 })
  })

  test('marks the boundary between what came before and after', async () => {
    const { dm } = open({ fresh_start_at: '2026-11-13T10:00:00Z' }, [
      said('Nachher.', '2026-11-13T10:05:00Z'),
      said('Vorher: HC-1.', '2026-11-13T09:00:00Z', true),
    ])
    await renderApp(`/c/${dm.id}`)
    const boundary = await screen.findByRole('separator', { name: /Neu begonnen/ })
    expect(boundary).toHaveTextContent(/bekommt Hilda nichts mehr/)
    const items = screen.getAllByRole('listitem')
    const at = (text: string) => items.findIndex((li) => li.textContent?.includes(text))
    expect(at('Vorher: HC-1.')).toBeLessThan(at('Neu begonnen'))
    expect(at('Neu begonnen')).toBeLessThan(at('Nachher.'))
  })

  test('the badge says how the mark ends', async () => {
    const { dm } = open({}, [said('Vorher: HC-1.', '2026-11-13T09:00:00Z', true)])
    const { user } = await renderApp(`/c/${dm.id}`)
    await user.click(await screen.findByRole('button', { name: /Persönlich/ }))
    expect(screen.getByText(/über deinen eigenen Zugang gelesen/)).toHaveTextContent(
      /„Neu beginnen“/,
    )
  })

  test('is not offered in a DM with another person', async () => {
    const { dm } = open({
      participants: [
        { id: 'me', name: 'Ich', is_active: true, type: 'user' },
        { id: BOB.id, name: BOB.name, is_active: true, type: 'user' },
      ],
    })
    await renderApp(`/c/${dm.id}`)
    await screen.findByRole('heading', { level: 1 })
    expect(screen.queryByRole('button', { name: 'Neu beginnen' })).toBeNull()
  })
})
