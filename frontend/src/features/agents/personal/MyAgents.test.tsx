import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Permission, Schemas } from '@/lib/api'
import { apiError, makeMe, mockApi, page, type Call } from '@/test/api'
import { makeConversation, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'

type Agent = Schemas['AgentOut']

const ME = 'me-1'
const OWN = '00000000-0000-7000-8000-0000000000b1'

function makeAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: OWN,
    name: 'Notizfuchs',
    intro: 'Sortiert meine Notizen.',
    kind: 'internal',
    instructions: '',
    connection_id: 'c-1',
    model: 'gpt-6-luna',
    responsible_user_id: ME,
    responsible_name: 'Mia Muster',
    owner_user_id: ME,
    status: 'active',
    max_steps: 25,
    max_runtime_seconds: 600,
    level: 2,
    version: 3,
    created_at: '2026-11-13T08:00:00Z',
    updated_at: '2026-11-13T08:00:00Z',
    ...overrides,
  }
}

function routes(permissions: Permission[], agents: Agent[], extra: object = {}) {
  const me = makeMe(['directory.read', ...permissions], { id: ME })
  return mockApi({
    ...shellRoutes(me),
    'GET /api/agents': page(agents),
    ...(extra as Record<string, object>),
  })
}

describe('my agents', () => {
  test('lists my own agents and makes a new one with just a name', async () => {
    const other = makeAgent({ id: 'x', name: 'Fremd', owner_user_id: null })
    const api = routes(['ai.use', 'agent.create_personal'], [makeAgent(), other], {
      'POST /api/agents': (call: Call) => ({
        status: 201,
        body: makeAgent({ id: 'new', name: (call.body as { name: string }).name }),
      }),
    })
    const { user } = await renderApp('/my-agents')
    const nav = await screen.findByRole('link', { name: 'Meine Agenten' })
    expect(nav).toHaveAttribute('href', '/my-agents')
    const list = await screen.findByRole('list', { name: 'Meine Agenten' })
    // An agent admin's list holds every agent; only my own show here.
    expect(within(list).getByRole('article', { name: 'Notizfuchs' })).toBeInTheDocument()
    expect(within(list).queryByRole('article', { name: 'Fremd' })).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Agent anlegen' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Name'), 'Leselampe')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(api.find('POST', '/api/agents')).toHaveLength(1))
    expect(api.find('POST', '/api/agents')[0]!.body).toEqual({
      name: 'Leselampe',
      intro: '',
      instructions: '',
      status: 'active',
      personal: true,
    })
  })

  test('the limit and the switch are put into words', async () => {
    routes(['ai.use', 'agent.create_personal'], [], {
      'POST /api/agents': apiError(409, 'agent.personal_limit'),
    })
    const { user } = await renderApp('/my-agents')
    expect(await screen.findByText('Du hast noch keine eigenen Agenten.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Agent anlegen' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Name'), 'Zu viel')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    expect(
      await within(dialog).findByText(/so viele eigene Agenten, wie erlaubt sind/),
    ).toBeInTheDocument()
  })

  test('switched off: no new agents, and the page says so', async () => {
    routes(['ai.use'], [makeAgent()])
    await renderApp('/my-agents')
    expect(
      await screen.findByText(/Persönliche Agenten sind in dieser Organisation ausgeschaltet/),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Agent anlegen' })).toBeNull()
  })

  test('pause, talk to, and delete one of my agents', async () => {
    const dm = makeConversation({ kind: 'dm', id: '00000000-0000-7000-8000-0000000000d9' })
    const api = routes(['ai.use', 'agent.create_personal'], [makeAgent()], {
      'PATCH /api/agents/:id': makeAgent({ status: 'paused', version: 4 }),
      'DELETE /api/agents/:id': { status: 204 },
      'POST /api/dms': dm,
      'GET /api/conversations/:id': dm,
      'GET /api/conversations/:id/messages': page([]),
      'POST /api/conversations/:id/read': { status: 204 },
    })
    const { user, router } = await renderApp('/my-agents')
    const card = await screen.findByRole('article', { name: 'Notizfuchs' })
    await user.click(within(card).getByRole('button', { name: 'Pausieren' }))
    await waitFor(() =>
      expect(api.find('PATCH', `/api/agents/${OWN}`)[0]?.body).toEqual({
        status: 'paused',
        version: 3,
      }),
    )
    await user.click(within(card).getByRole('button', { name: 'Agent Notizfuchs löschen' }))
    const confirm = await screen.findByRole('dialog')
    await user.click(within(confirm).getByRole('button', { name: 'Löschen' }))
    await waitFor(() => expect(api.find('DELETE', `/api/agents/${OWN}`)).toHaveLength(1))
    expect(api.find('DELETE', `/api/agents/${OWN}`)[0]!.query.get('version')).toBe('3')
    await user.click(within(card).getByRole('button', { name: 'Gespräch öffnen' }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/c/${dm.id}`))
    expect(api.find('POST', '/api/dms')[0]!.body).toEqual({ agent_id: OWN })
  })

  test("an agent's own page caps the level at 2 and says why", async () => {
    routes(['ai.use', 'agent.create_personal'], [], {
      'GET /api/agents/:id': makeAgent(),
      'GET /api/agents/:id/tools': {
        agent_id: OWN,
        level: 2,
        max_level: 2,
        version: 3,
        tools: [],
      },
      'GET /api/agents/:id/spaces': page([
        { id: 'p', name: 'Mia (persönlich)', kind: 'personal', role: 'editor' },
      ]),
    })
    await renderApp(`/my-agents/${OWN}`)
    const levels = await screen.findByRole('group', { name: 'Autonomiestufe' })
    expect(within(levels).queryByRole('radio', { name: /Stufe 3/ })).toBeNull()
    expect(
      within(levels).getByText('Persönliche Agenten arbeiten höchstens auf Stufe 2.'),
    ).toBeInTheDocument()
    expect(await screen.findByText('Mia (persönlich)')).toBeInTheDocument()
  })
})

describe('personal agents in the administration', () => {
  test("the agents list marks someone's personal agent with the owner's name", async () => {
    routes(['agent.manage', 'ai.manage'], [makeAgent({ responsible_name: 'Lea Löwe' })], {
      'GET /api/ai/connections': page([]),
    })
    await renderApp('/admin/agents')
    const card = await screen.findByRole('article', { name: 'Notizfuchs' })
    expect(within(card).getByText('Persönlich: Lea Löwe')).toBeInTheDocument()
  })

  test('the AI administration switches personal agents off', async () => {
    const api = routes(['ai.manage'], [], {
      'GET /api/ai/connections': page([
        {
          id: 'c-1',
          name: 'Stub',
          kind: 'local',
          models: ['m'],
          purpose: 'chat',
          enabled: true,
        },
      ]),
      'GET /api/ai/assignments': { default: null, personal_agents: true, version: 7 },
      'GET /api/ai/assignments/groups': page([]),
      'GET /api/ai/assignments/users': page([]),
      'PUT /api/ai/assignments/personal-agents': {
        default: null,
        personal_agents: false,
        version: 8,
      },
    })
    const { user } = await renderApp('/admin/ai/assignments')
    const box = await screen.findByRole('checkbox', { name: 'Persönliche Agenten erlauben' })
    expect(box).toBeChecked()
    await user.click(box)
    await waitFor(() =>
      expect(api.find('PUT', '/api/ai/assignments/personal-agents')[0]?.body).toEqual({
        enabled: false,
        version: 7,
      }),
    )
  })
})
