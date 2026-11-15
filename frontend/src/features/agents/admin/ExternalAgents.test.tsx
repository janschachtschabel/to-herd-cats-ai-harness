import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Schemas } from '@/lib/api'
import { makeMe, mockApi, page } from '@/test/api'
import { EXTERNAL_ID, externalTools, makeExternalAgent } from '@/test/external'
import { renderApp } from '@/test/render'
import { created, makeToken } from '@/test/tokens'

type Agent = Schemas['AgentOut']

const SECRET = 'herd_agt_wegwerf-nur-im-test-000000000000000000'
const SPACE_ID = '00000000-0000-7000-8000-0000000005a1'
const me = makeMe(['agent.manage', 'ai.manage', 'directory.read'])

const shell = {
  'GET /api/auth/me': me,
  'GET /api/spaces': page([]),
}

function agentPage(extra: Record<string, unknown> = {}) {
  return {
    ...shell,
    'GET /api/agents/:id': makeExternalAgent(),
    'GET /api/agents/:id/tools': externalTools(),
    'GET /api/agents/:id/spaces': page([
      { id: SPACE_ID, name: 'Werkstatt', kind: 'team', role: 'editor' },
    ]),
    'GET /api/agents/:id/tokens': page([]),
    ...extra,
  }
}

describe('external agents', () => {
  test('are created without a connection: no model, level 1 or 2, a responsible person', async () => {
    const agents: Agent[] = []
    const api = mockApi({
      ...shell,
      'GET /api/ai/connections': page([]),
      'GET /api/agents': () => page(agents),
      'POST /api/agents': (call) => {
        const made = makeExternalAgent(call.body as Partial<Agent>)
        agents.push(made)
        return { status: 201, body: made }
      },
    })
    const { user } = await renderApp('/admin/agents')
    expect(screen.getByRole('button', { name: 'Agent anlegen' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Externen Agenten anlegen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Externen Agenten anlegen' })
    expect(within(dialog).queryByLabelText('Modell')).not.toBeInTheDocument()
    expect(within(dialog).queryByLabelText('Anweisungen')).not.toBeInTheDocument()
    await user.type(within(dialog).getByLabelText('Name'), 'Codi')
    await user.type(within(dialog).getByLabelText('Kurzvorstellung'), 'Arbeitet von außen.')
    await user.click(within(dialog).getByRole('radio', { name: /Stufe 1/ }))
    await user.selectOptions(within(dialog).getByLabelText('Status'), 'Aktiv')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(api.find('POST', '/api/agents')).toHaveLength(1))
    expect(api.find('POST', '/api/agents')[0]!.body).toEqual({
      kind: 'external',
      name: 'Codi',
      intro: 'Arbeitet von außen.',
      responsible_user_id: me.user.id,
      status: 'active',
      level: 1,
    })
    const card = await screen.findByRole('article', { name: 'Codi' })
    expect(within(card).getByText('Extern über MCP')).toBeInTheDocument()
    expect(within(card).queryByText(/Modell/)).not.toBeInTheDocument()
    expect(within(card).queryByRole('link', { name: 'Läufe' })).not.toBeInTheDocument()
    expect(within(card).getByRole('link', { name: 'Stufe, Werkzeuge, Token' })).toBeInTheDocument()
  })

  test('an external agent is changed without model fields, at its version', async () => {
    const agent = makeExternalAgent()
    const api = mockApi({
      ...shell,
      'GET /api/ai/connections': page([]),
      'GET /api/agents': page([agent]),
      [`PATCH /api/agents/${agent.id}`]: (call) => ({ ...agent, ...(call.body as object) }),
    })
    const { user } = await renderApp('/admin/agents')
    const card = await screen.findByRole('article', { name: 'Codi' })
    await user.click(within(card).getByRole('button', { name: 'Bearbeiten' }))
    const dialog = await screen.findByRole('dialog', { name: 'Codi bearbeiten' })
    expect(within(dialog).queryByLabelText('Modell')).not.toBeInTheDocument()
    await user.clear(within(dialog).getByLabelText('Name'))
    await user.type(within(dialog).getByLabelText('Name'), 'Codi 2')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(api.find('PATCH', `/api/agents/${agent.id}`)).toHaveLength(1))
    expect(api.find('PATCH', `/api/agents/${agent.id}`)[0]!.body).toMatchObject({
      name: 'Codi 2',
      version: 3,
    })
    expect(api.find('PATCH', `/api/agents/${agent.id}`)[0]!.body).not.toHaveProperty('model')
  })

  test('its page shows what counts for it: level up to 2, its tools over MCP, no runs', async () => {
    mockApi(agentPage())
    await renderApp(`/admin/agents/${EXTERNAL_ID}`)
    expect(await screen.findByRole('heading', { name: 'Codi' })).toBeInTheDocument()
    expect(screen.getByText('Extern über MCP')).toBeInTheDocument()
    expect(screen.getAllByRole('radio').map((r) => r.closest('label')?.textContent)).toEqual([
      expect.stringContaining('Stufe 1'),
      expect.stringContaining('Stufe 2'),
    ])
    expect(screen.getByText(/höchstens Stufe 2/)).toBeInTheDocument()
    expect(screen.getByText(/sieht die eigenen Tickets\. Ändert nichts/)).toBeInTheDocument()
    expect(screen.queryByText(/das Gespräch und antwortet/)).not.toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Werkzeuge über MCP' })
    expect(within(table).getByText('Suchen')).toBeInTheDocument()
    expect(within(table).getByText('Ticket kommentieren')).toBeInTheDocument()
    expect(within(table).queryByText('Rückfrage stellen')).not.toBeInTheDocument()
    expect(within(table).queryByText('Gedächtnis pflegen')).not.toBeInTheDocument()
    expect(within(table).queryByText('Seite direkt ändern')).not.toBeInTheDocument()
    const choice = within(table).getByRole('combobox', { name: 'Freigabe für Suchen' })
    expect(
      within(choice)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Erlaubt', 'Gesperrt'])
    expect(screen.getByText(/Nur „Erlaubt“ zählt/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Skills' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Aufgaben' })).not.toBeInTheDocument()
  })

  test('its tokens: created with the clear text once and the setup for the agent', async () => {
    const made = makeToken({ name: 'Pipeline', kind: 'agent', agent_id: EXTERNAL_ID })
    const api = mockApi(
      agentPage({
        [`POST /api/agents/${EXTERNAL_ID}/tokens`]: { status: 201, body: created(made, SECRET) },
      }),
    )
    const { user } = await renderApp(`/admin/agents/${EXTERNAL_ID}`)
    const section = await screen.findByRole('region', { name: 'Token des Agenten' })
    expect(within(section).getByText('Codi hat noch kein Token.')).toBeInTheDocument()
    await user.click(within(section).getByRole('button', { name: 'Token anlegen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Zugangstoken anlegen' })
    await user.click(within(dialog).getByRole('radio', { name: 'Nur ausgewählte Bereiche' }))
    await user.click(within(dialog).getByRole('checkbox', { name: 'Werkstatt' }))
    await user.type(within(dialog).getByLabelText('Name'), 'Pipeline')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() =>
      expect(api.find('POST', `/api/agents/${EXTERNAL_ID}/tokens`)).toHaveLength(1),
    )
    expect(api.find('POST', `/api/agents/${EXTERNAL_ID}/tokens`)[0]!.body).toMatchObject({
      name: 'Pipeline',
      mode: 'read',
      space_ids: [SPACE_ID],
    })
    const shown = await screen.findByRole('dialog', { name: 'Dein neues Token: Pipeline' })
    expect(within(shown).getByLabelText('Token')).toHaveValue(SECRET)
    expect(within(shown).getByText(/Bearer \$HERD_AGENT_TOKEN/)).toBeInTheDocument()
    expect(within(shown).getByText(/list_my_tickets/)).toBeInTheDocument()
  })
})
