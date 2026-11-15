import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Schemas } from '@/lib/api'
import { apiError, makeMe, makeUser, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

type Agent = Schemas['AgentOut']

const CONNECTION = {
  id: '00000000-0000-7000-8000-00000000c001',
  name: 'Stub',
  kind: 'local',
  base_url: 'http://127.0.0.1:8099/v1',
  secret: { set: false, kind: null },
  models: ['gpt-6-luna', 'gpt-6-luna-mini'],
  param_family: 'max_tokens',
  extra_body: {},
  supports_tools: true,
  data_location: 'local',
  max_concurrency: 4,
  requests_per_minute: 60,
  purpose: 'chat',
  enabled: true,
  prices: {},
  streaming: true,
  version: 1,
  created_at: '2026-11-13T08:00:00Z',
  updated_at: '2026-11-13T08:00:00Z',
} satisfies Schemas['ConnectionOut']

const me = makeMe(['ai.manage', 'agent.manage', 'directory.read', 'user.manage'])

function makeAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: '00000000-0000-7000-8000-0000000000a1',
    name: 'Hilda',
    intro: 'Hilft beim Handbuch.',
    kind: 'internal',
    instructions: 'Antworte kurz.',
    connection_id: CONNECTION.id,
    model: 'gpt-6-luna',
    responsible_user_id: me.user.id,
    responsible_name: 'Mia Muster',
    owner_user_id: null,
    status: 'active',
    max_steps: 25,
    max_runtime_seconds: 600,
    level: 2,
    version: 2,
    created_at: '2026-11-13T08:00:00Z',
    updated_at: '2026-11-13T08:00:00Z',
    ...overrides,
  }
}

describe('agents administration', () => {
  test('an admin creates an agent: model from a connection, responsible person, status', async () => {
    const agents: Agent[] = []
    const api = mockApi({
      'GET /api/auth/me': me,
      'GET /api/spaces': page([]),
      'GET /api/ai/connections': page([CONNECTION]),
      'GET /api/agents': () => page(agents),
      'POST /api/agents': (call) => {
        const created = makeAgent(call.body as Partial<Agent>)
        agents.push(created)
        return { status: 201, body: created }
      },
    })
    const { user } = await renderApp('/admin/agents')
    expect(await screen.findByText('Noch keine Agenten.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Agent anlegen' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Name'), 'Hilda')
    await user.type(within(dialog).getByLabelText('Kurzvorstellung'), 'Hilft beim Handbuch.')
    await user.type(within(dialog).getByLabelText('Anweisungen'), 'Antworte kurz.')
    await user.selectOptions(within(dialog).getByLabelText('Modell'), 'gpt-6-luna-mini')
    await user.selectOptions(within(dialog).getByLabelText('Status'), 'Aktiv')
    expect(within(dialog).getByRole('combobox', { name: 'Verantwortliche Person' })).toHaveValue(
      'Mia Muster',
    )
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(api.find('POST', '/api/agents')[0]?.body).toEqual({
      name: 'Hilda',
      intro: 'Hilft beim Handbuch.',
      instructions: 'Antworte kurz.',
      connection_id: CONNECTION.id,
      model: 'gpt-6-luna-mini',
      responsible_user_id: me.user.id,
      status: 'active',
      max_steps: 25,
      max_runtime_seconds: 600,
      level: 2,
      personal: false, // an organisation agent (the schema's default)
      kind: 'internal', // with a model of its own (the schema's default)
    })
    expect(await screen.findByRole('article', { name: 'Hilda' })).toBeInTheDocument()
  })

  test('pausing sends the version; deleting one that talked explains to pause instead', async () => {
    const agent = makeAgent()
    const api = mockApi({
      'GET /api/auth/me': me,
      'GET /api/spaces': page([]),
      'GET /api/ai/connections': page([CONNECTION]),
      'GET /api/agents': page([agent]),
      'GET /api/admin/users': page([makeUser({ id: me.user.id, name: 'Mia Muster' })]),
      'PATCH /api/agents/:id': { ...agent, status: 'paused', version: 3 },
      'DELETE /api/agents/:id': apiError(409, 'agent.in_use'),
    })
    const { user } = await renderApp('/admin/agents')
    const card = await screen.findByRole('article', { name: 'Hilda' })
    expect(
      within(card).getByText('Modell gpt-6-luna über Stub · höchstens 25 Schritte, 600 s'),
    ).toBeInTheDocument()
    await user.click(within(card).getByRole('button', { name: 'Pausieren' }))
    await waitFor(() =>
      expect(api.find('PATCH', `/api/agents/${agent.id}`)[0]?.body).toEqual({
        status: 'paused',
        version: 2,
      }),
    )
    await user.click(within(card).getByRole('button', { name: 'Agent Hilda löschen' }))
    const confirm = await screen.findByRole('dialog')
    await user.click(within(confirm).getByRole('button', { name: 'Löschen' }))
    expect(await within(confirm).findByText(/Pausiere ihn stattdessen/)).toBeInTheDocument()
  })

  test('editing shows the responsible person by name and the agent version on save', async () => {
    // The name comes with the agent: no people list (whose first page may not hold it).
    const agent = makeAgent({ responsible_name: 'Paul Pfeffer' })
    const api = mockApi({
      'GET /api/auth/me': me,
      'GET /api/spaces': page([]),
      'GET /api/ai/connections': page([CONNECTION]),
      'GET /api/agents': page([agent]),
      'GET /api/admin/users': page([makeUser({ id: me.user.id, name: 'Mia Muster' })]),
      'PATCH /api/agents/:id': (call) => ({ ...agent, ...(call.body as object), version: 3 }),
    })
    const { user } = await renderApp('/admin/agents')
    const card = await screen.findByRole('article', { name: 'Hilda' })
    await user.click(within(card).getByRole('button', { name: 'Bearbeiten' }))
    const dialog = await screen.findByRole('dialog')
    expect(await within(dialog).findByDisplayValue('Paul Pfeffer')).toBeInTheDocument()
    await user.clear(within(dialog).getByLabelText('Name'))
    await user.type(within(dialog).getByLabelText('Name'), 'Hilde')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() =>
      expect(api.find('PATCH', `/api/agents/${agent.id}`)[0]?.body).toMatchObject({
        name: 'Hilde',
        version: 2,
      }),
    )
  })
})
