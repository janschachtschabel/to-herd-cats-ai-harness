import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, test } from 'vitest'
import { clearPending } from '@/features/messaging/conversation/pending'
import { type Call, makeEntry, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes, written } from '@/test/messaging'
import { renderApp } from '@/test/render'

afterEach(() => clearPending())

const CODI = { id: '00000000-0000-7000-8000-0000000000e1', name: 'Codi' }
const codi = makeEntry({ type: 'agent', ...CODI, kind: 'external' })
const me = makeMe(['directory.read', 'ai.use'])

describe('external agents in pickers and conversations', () => {
  test('the mention picker marks one; mentioning it says it does not answer by itself', async () => {
    const space = makeSpace({ id: 'space-1', name: 'Werkstatt', my_role: 'editor' })
    const channel = makeConversation({ space_id: space.id })
    const api = mockApi({
      ...shellRoutes(me, [space]),
      'GET /api/spaces/:id': space,
      'GET /api/conversations/:id': channel,
      'GET /api/conversations/:id/messages': page([]),
      'POST /api/conversations/:id/read': { status: 204 },
      'GET /api/directory': page([codi]),
      'POST /api/conversations/:id/messages': (call: Call) => {
        const body = call.body as { body_md: string; client_id: string }
        const sent = makeMessage({ body_md: body.body_md, client_id: body.client_id })
        return {
          ...written(sent),
          agent_run: { id: null, reason: 'agent.external', agent_id: CODI.id },
        }
      },
    })
    const { user } = await renderApp(`/c/${channel.id}`)
    const box = await screen.findByRole('combobox', { name: 'Nachricht an #allgemein' })
    await user.type(box, '@co')
    const option = await screen.findByRole('option', { name: /Codi/ })
    expect(within(option).getByText('extern')).toBeInTheDocument()
    expect(within(option).getByText('Externer Agent, antwortet nicht von selbst')).toHaveClass(
      'sr-only',
    )
    await user.click(option)
    await user.type(box, 'schau mal{Enter}')
    await waitFor(() =>
      expect(api.find('POST', `/api/conversations/${channel.id}/messages`)).toHaveLength(1),
    )
    expect(await screen.findByText(/arbeitet von außen über MCP/)).toBeInTheDocument()
  })

  test('the DM dialog explains an external agent instead of opening a talk with it', async () => {
    const api = mockApi({
      ...shellRoutes(me, [makeSpace()]),
      'GET /api/directory': (call) => page(call.query.get('type') === 'agent' ? [codi] : []),
    })
    const { user } = await renderApp('/spaces')
    await user.click(await screen.findByRole('button', { name: 'Direktnachricht beginnen' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('combobox', { name: 'Agent' }))
    await user.click(await within(dialog).findByRole('option', { name: /Codi/ }))
    expect(within(dialog).getByText(/Codi arbeitet von außen über MCP/)).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Gespräch öffnen' })).toBeDisabled()
    expect(api.find('POST', '/api/dms')).toHaveLength(0)
  })

  test('a direct message with one says so in its header', async () => {
    const dm = makeConversation({
      kind: 'dm',
      space_id: null,
      name: null,
      participants: [
        { id: me.user.id, name: me.user.name, is_active: true, type: 'user' },
        { id: CODI.id, name: CODI.name, is_active: true, type: 'agent' },
      ],
    })
    mockApi({
      ...shellRoutes(me),
      'GET /api/conversations/:id': dm,
      'GET /api/conversations/:id/messages': page([]),
      'POST /api/conversations/:id/read': { status: 204 },
      'GET /api/agents/:id/profile': {
        id: CODI.id,
        name: CODI.name,
        kind: 'external',
        intro: 'Arbeitet Tickets ab.',
        status: 'active',
      },
    })
    await renderApp(`/c/${dm.id}`)
    expect(await screen.findByText(/antwortet hier nicht von selbst/)).toBeInTheDocument()
  })
})
