import { screen, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Message } from '@/lib/api'
import { makeMe, makeSpace, mockApi, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { HILDA, makeApproval, makeRun } from '@/test/runs'

const TOOL = 'ext_0123456789ab_create_issue'
const external = {
  server_id: '00000000-0000-7000-8000-00000000c5f1',
  tool_id: '00000000-0000-7000-8000-00000000c5f9',
}

function card(id: string, body: string): Message {
  return makeMessage({
    kind: 'approval',
    author: { type: 'agent', id: HILDA.id, name: HILDA.name },
    body_md: body,
    run_id: 'run-1',
    card: { type: 'approval', id },
  })
}

function channelWith(approval: ReturnType<typeof makeApproval>, meId: string) {
  const me = makeMe(['directory.read', 'ai.use'], { id: meId })
  const space = makeSpace({ id: 'space-1', name: 'Handbuch', my_role: 'editor' })
  const channel = makeConversation({ space_id: space.id })
  mockApi({
    ...shellRoutes(me, [space]),
    'GET /api/spaces/:id': space,
    'GET /api/conversations/:id': channel,
    'GET /api/conversations/:id/messages': page([
      { ...card(approval.id, approval.summary), conversation_id: channel.id },
    ]),
    'POST /api/conversations/:id/read': { status: 204 },
    'GET /api/runs/:id': makeRun({ id: 'run-1', state: 'waiting', stop_reason: null }),
    'GET /api/approvals/:id': approval,
  })
  return channel
}

describe('a release card for an external tool', () => {
  test('the person asked reads "server · tool" and exactly what goes to the server', async () => {
    const approval = makeApproval({
      id: 'ap-x1',
      tool: TOOL,
      summary: 'GitHub · create_issue',
      // An external tool's arguments name no page or ticket of ours, whatever their keys.
      args: { repo: 'acme/app', title: 'Fehler im Export', key: 'HC-12' },
      diff_url: null,
      external,
    })
    const channel = channelWith(approval, 'asker')
    await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Freigabe' })
    expect(
      within(shown).getByText('Freigabe erbeten: externes Werkzeug create_issue'),
    ).toBeInTheDocument()
    expect(within(shown).getByText('GitHub · create_issue')).toBeInTheDocument()
    expect(within(shown).getByText(/gehen genau so an den externen Server/)).toBeVisible()
    const args = within(shown).getByLabelText('Argumente für den externen Server')
    expect(args).toBeVisible()
    expect(args).toHaveTextContent('"repo": "acme/app"')
    expect(args).toHaveTextContent('"title": "Fehler im Export"')
    expect(within(shown).queryByRole('link', { name: /Ticket/ })).toBeNull()
    expect(within(shown).getByRole('button', { name: 'Freigeben' })).toBeVisible()
  })

  test('anyone else sees "server · tool" and that the arguments are the asked person’s', async () => {
    const approval = makeApproval({
      id: 'ap-x2',
      tool: TOOL,
      summary: 'GitHub · create_issue',
      args: null,
      diff_url: null,
      external,
    })
    const channel = channelWith(approval, 'responsible')
    await renderApp(`/c/${channel.id}`)
    const shown = await screen.findByRole('region', { name: 'Freigabe' })
    expect(within(shown).getByText('GitHub · create_issue')).toBeInTheDocument()
    expect(within(shown).getByText(/Die Argumente sieht nur die gefragte Person/)).toBeVisible()
    expect(within(shown).queryByLabelText('Argumente für den externen Server')).toBeNull()
    expect(within(shown).queryByRole('button')).toBeNull()
  })
})
