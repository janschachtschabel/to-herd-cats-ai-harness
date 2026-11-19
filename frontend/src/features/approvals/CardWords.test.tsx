import { screen, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Message } from '@/lib/api'
import { makeMe, makeSpace, mockApi, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { HILDA, makeApproval, makeQuestion, makeRun } from '@/test/runs'

const hilda = { type: 'agent' as const, id: HILDA.id, name: HILDA.name }

/** A channel with one card message, seen by the agent's responsible person (who may
 *  see the card, but was not asked). */
function seenByOthers(type: 'approval' | 'question', id: string, body: string, card: object) {
  const message: Message = makeMessage({
    kind: type,
    author: hilda,
    body_md: body,
    run_id: 'run-1',
    card: { type, id },
  })
  const me = makeMe(['directory.read', 'ai.use'], { id: 'responsible' })
  const space = makeSpace({ id: 'space-1', name: 'Handbuch', my_role: 'editor' })
  const channel = makeConversation({ space_id: space.id })
  mockApi({
    ...shellRoutes(me, [space]),
    'GET /api/spaces/:id': space,
    'GET /api/conversations/:id': channel,
    'GET /api/conversations/:id/messages': page([{ ...message, conversation_id: channel.id }]),
    'POST /api/conversations/:id/read': { status: 204 },
    'GET /api/runs/:id': makeRun({ id: 'run-1', state: 'waiting', stop_reason: null }),
    [`GET /api/${type === 'approval' ? 'approvals' : 'questions'}/:id`]: card,
  })
  return channel
}

describe("an agent's words on a card are the asked person's to read", () => {
  test('someone else reads a redacted question as the message has it', async () => {
    const redacted = makeQuestion({ id: 'q-9', question: null, redacted: true })
    const channel = seenByOthers('question', 'q-9', 'Für welches Jahr?', redacted)
    await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Rückfrage' })
    expect(await within(shown).findByText('Für welches Jahr?')).toBeInTheDocument()
    expect(within(shown).queryByRole('textbox')).toBeNull()
  })

  test('someone else reads a rejection without its reason, and says so', async () => {
    const rejected = makeApproval({
      id: 'ap-9',
      state: 'rejected',
      decided_by: 'asker',
      decided_at: '2026-11-14T10:00:00Z',
      args: null,
      diff_url: null,
      reason: null,
      redacted: true,
    })
    const channel = seenByOthers('approval', 'ap-9', rejected.tool, rejected)
    await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Freigabe' })
    expect(await within(shown).findByText('Abgelehnt')).toBeInTheDocument()
    expect(
      within(shown).getByText('Eine Begründung sieht nur die Person, die gefragt wurde.'),
    ).toBeInTheDocument()
    expect(within(shown).queryByText(/^Begründung:/)).toBeNull()
  })

  test('someone else reads an approval without its summary, and says so', async () => {
    const theirs = makeApproval({
      id: 'ap-8',
      tool: 'set_ticket_status',
      summary: null,
      args: null,
      diff_url: null,
      redacted: true,
    })
    const channel = seenByOthers('approval', 'ap-8', 'set_ticket_status', theirs)
    await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Freigabe' })
    expect(
      await within(shown).findByText('Die Einzelheiten sieht nur die Person, die gefragt wurde.'),
    ).toBeInTheDocument()
    expect(within(shown).queryByText(/key=/)).toBeNull()
  })
})
