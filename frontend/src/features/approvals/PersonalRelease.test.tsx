import { screen, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Approval } from '@/features/approvals/queries'
import { makeMe, makeSpace, mockApi, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { HILDA, makeApproval, makeRun } from '@/test/runs'

const CHANNEL = '00000000-0000-7000-8000-0000000000c1'

/** Her DM with one release card of a run under the personal mark. */
function dmWith(approval: Approval, meId = 'asker') {
  const me = makeMe(['directory.read', 'ai.use'], { id: meId })
  const space = makeSpace({ id: 'space-1', name: 'Handbuch', my_role: 'editor' })
  const dm = makeConversation({ kind: 'dm', space_id: null, name: null })
  const message = makeMessage({
    kind: 'approval',
    author: { type: 'agent', id: HILDA.id, name: HILDA.name },
    body_md: approval.summary,
    run_id: 'run-1',
    card: { type: 'approval', id: approval.id },
    conversation_id: dm.id,
  })
  mockApi({
    ...shellRoutes(me, [space]),
    'GET /api/conversations/:id': dm,
    'GET /api/conversations/:id/messages': page([message]),
    'POST /api/conversations/:id/read': { status: 204 },
    'GET /api/runs/:id': makeRun({ id: 'run-1', state: 'waiting', stop_reason: null }),
    'GET /api/approvals/:id': approval,
  })
  return dm
}

const release = (overrides: Partial<Approval> = {}) =>
  makeApproval({
    id: 'ap-p1',
    tool: 'post_message',
    summary: `post_message: conversation_id=${CHANNEL}`,
    args: { conversation_id: CHANNEL, text: 'Für alle: HC-1 ist erledigt.' },
    diff_url: null,
    personal: true,
    ...overrides,
  })

describe('a release card under the personal mark (module review M8 2, G2)', () => {
  test('says why it asks and shows exactly what would be written, open', async () => {
    const dm = dmWith(release())
    await renderApp(`/c/${dm.id}`)
    const shown = await screen.findByRole('region', { name: 'Freigabe' })
    expect(within(shown).getByText(/^Persönlich:/)).toHaveTextContent(
      /genau der folgende Inhalt geschrieben/,
    )
    const args = within(shown).getByText('Angaben des Aufrufs').closest('details')
    expect(args).toHaveAttribute('open')
    expect(args).toHaveTextContent('Für alle: HC-1 ist erledigt.')
  })

  test('an ordinary release card keeps its arguments folded and says nothing of it', async () => {
    const dm = dmWith(release({ personal: false }))
    await renderApp(`/c/${dm.id}`)
    const shown = await screen.findByRole('region', { name: 'Freigabe' })
    expect(within(shown).queryByText(/^Persönlich:/)).toBeNull()
    expect(within(shown).getByText('Angaben des Aufrufs').closest('details')).not.toHaveAttribute(
      'open',
    )
  })

  test('someone else sees the note but not the content', async () => {
    const dm = dmWith(release({ args: null }), 'someone-else')
    await renderApp(`/c/${dm.id}`)
    const shown = await screen.findByRole('region', { name: 'Freigabe' })
    expect(within(shown).getByText(/^Persönlich:/)).toBeInTheDocument()
    expect(within(shown).queryByText(/Für alle/)).toBeNull()
  })
})
