import { screen, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Message } from '@/lib/api'
import { makeMe, mockApi, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'

const AGENT = { id: '00000000-0000-7000-8000-0000000000a1', name: 'Hilda' }

/** Her DM alone with the agent (the only place a marked message can be). */
function dmWith(messages: Message[]) {
  const me = makeMe(['directory.read', 'ai.use'])
  const dm = makeConversation({
    kind: 'dm',
    space_id: null,
    name: null,
    participants: [
      { id: me.user.id, name: me.user.name, is_active: true, type: 'user' },
      { id: AGENT.id, name: AGENT.name, is_active: true, type: 'agent' },
    ],
  })
  mockApi({
    ...shellRoutes(me),
    'GET /api/conversations/:id': dm,
    'GET /api/conversations/:id/messages': page(
      messages.map((m) => ({ ...m, conversation_id: dm.id })),
    ),
    'POST /api/conversations/:id/read': { status: 204 },
    'GET /api/agents/:id/profile': { id: AGENT.id, name: AGENT.name, intro: '', status: 'active' },
    'GET /api/runs/:id/events': page([]),
  })
  return dm
}

const answer = (body: string, personal: boolean, at: string) =>
  makeMessage({
    kind: 'agent',
    author: { type: 'agent', id: AGENT.id, name: AGENT.name },
    body_md: body,
    personal,
    created_at: at,
  })

describe('a personal message (module review M8 2, G2)', () => {
  test('carries the mark, which says on request what it means', async () => {
    const dm = dmWith([
      answer('Deine Issues: HC-1 und HC-2.', true, '2026-11-13T09:00:00Z'),
      answer('Gern geschehen.', false, '2026-11-13T09:05:00Z'),
    ])
    const { user } = await renderApp(`/c/${dm.id}`)
    const answers = await screen.findAllByRole('article', { name: 'Nachricht von Hilda' })
    const marked = answers.find((a) => a.textContent?.includes('Deine Issues'))
    const plain = answers.find((a) => a.textContent?.includes('Gern geschehen'))
    expect(within(plain!).queryByRole('button', { name: /Persönlich/ })).toBeNull()
    const badge = within(marked!).getByRole('button', { name: /Persönlich/ })
    expect(badge).toHaveAttribute('aria-expanded', 'false')
    expect(within(marked!).queryByText(/über deinen eigenen Zugang gelesen/)).toBeNull()

    await user.click(badge)
    expect(badge).toHaveAttribute('aria-expanded', 'true')
    const said = within(marked!).getByText(/über deinen eigenen Zugang gelesen/)
    expect(said).toHaveTextContent(/vorher zur Freigabe vor/)
    await user.click(badge)
    expect(within(marked!).queryByText(/über deinen eigenen Zugang gelesen/)).toBeNull()
  })
})
