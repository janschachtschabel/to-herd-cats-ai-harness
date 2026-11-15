import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Schemas } from '@/lib/api'
import { makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

type Tools = Schemas['AgentToolsOut']
type AgentTool = Schemas['AgentToolOut']

const me = makeMe(['agent.manage', 'ai.manage', 'directory.read'])
const AGENT_ID = '00000000-0000-7000-8000-0000000000a2'
const GITHUB = '00000000-0000-7000-8000-00000000c5f1'
const GITLAB = '00000000-0000-7000-8000-00000000c5f2'

function external(
  name: string,
  server: [string, string],
  tool: Partial<AgentTool>,
  usable = true,
): AgentTool {
  return {
    name: `ext_0123456789ab_${name}`,
    level: 2,
    effect: 'read',
    default: 'block',
    entry: null,
    effective: 'block',
    external: {
      server_id: server[0],
      server_name: server[1],
      tool_id: `tool-${name}`,
      tool_name: name,
      usable,
    },
    ...tool,
  }
}

const github: [string, string] = [GITHUB, 'GitHub']
const gitlab: [string, string] = [GITLAB, 'GitLab']

function tools(overrides: Partial<Tools> = {}): Tools {
  return {
    agent_id: AGENT_ID,
    level: 2,
    max_level: 4,
    version: 7,
    tools: [
      {
        name: 'search',
        level: 1,
        effect: 'read',
        default: 'allow',
        entry: null,
        effective: 'allow',
        external: null,
      },
      external('list_issues', github, {}),
      external('create_issue', github, {
        level: 4,
        effect: 'write',
        entry: 'confirm',
        effective: 'block',
      }),
      external('get_project', gitlab, { entry: 'allow', effective: 'block' }, false),
    ],
    ...overrides,
  }
}

function setup(shown: Tools, extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /api/auth/me': me,
    'GET /api/spaces': page([]),
    'GET /api/agents/:id': {
      id: AGENT_ID,
      name: 'Hilda',
      intro: null,
      instructions: '',
      connection_id: null,
      model: null,
      responsible_user_id: me.user.id,
      responsible_name: 'Mia Muster',
      owner_user_id: null,
      status: 'active',
      max_steps: 25,
      max_runtime_seconds: 600,
      level: shown.level,
      version: 7,
      created_at: '2026-11-13T08:00:00Z',
      updated_at: '2026-11-13T08:00:00Z',
    },
    'GET /api/agents/:id/tools': shown,
    'GET /api/agents/:id/spaces': page([]),
    'GET /api/agents/:id/skills': { version: 7, skills: [] },
    ...extra,
  })
}

describe('external tools in an agent’s grants', () => {
  test('after the catalog, grouped by server; unusable ones marked; writes always released', async () => {
    setup(tools())
    await renderApp(`/admin/agents/${AGENT_ID}`)
    const table = await screen.findByRole('table', { name: 'Werkzeuge des Agenten' })
    const rows = within(table).getAllByRole('row')
    const labels = rows.map((row) => row.textContent ?? '')
    const githubAt = labels.findIndex((text) => text.includes('Externe Werkzeuge · GitHub'))
    const gitlabAt = labels.findIndex((text) => text.includes('Externe Werkzeuge · GitLab'))
    const searchAt = labels.findIndex((text) => text.includes('Suchen'))
    expect(searchAt).toBeGreaterThan(0)
    expect(githubAt).toBeGreaterThan(searchAt)
    expect(gitlabAt).toBeGreaterThan(githubAt)

    const read = within(table).getByRole('row', { name: /list_issues/ })
    const readChoice = within(read).getByRole('combobox', { name: 'Freigabe für list_issues' })
    expect(
      within(readChoice)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Nicht zugeteilt', 'Erlaubt', 'Nur nach Freigabe'])

    const write = within(table).getByRole('row', { name: /create_issue/ })
    expect(within(write).getByText('Handelt nach außen: jeder Aufruf nach Freigabe')).toBeVisible()
    expect(within(write).getByText('Wirkt erst ab Stufe 4')).toBeVisible()
    const writeChoice = within(write).getByRole('combobox', { name: 'Freigabe für create_issue' })
    expect(writeChoice).toHaveValue('confirm')
    expect(
      within(writeChoice)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Nicht zugeteilt', 'Nur nach Freigabe'])

    const unusable = within(table).getByRole('row', { name: /get_project/ })
    expect(within(unusable).getByText(/Nicht nutzbar/)).toBeVisible()
  })

  test('saving keeps the entries made, adds the new grant, drops what is not granted', async () => {
    const api = setup(tools(), { 'PUT /api/agents/:id/tools': tools({ version: 8 }) })
    const { user } = await renderApp(`/admin/agents/${AGENT_ID}`)
    const table = await screen.findByRole('table', { name: 'Werkzeuge des Agenten' })
    await user.selectOptions(
      within(table).getByRole('combobox', { name: 'Freigabe für list_issues' }),
      'allow',
    )
    await user.click(screen.getByRole('button', { name: 'Freigaben speichern' }))
    await waitFor(() =>
      expect(api.find('PUT', `/api/agents/${AGENT_ID}/tools`)[0]?.body).toEqual({
        tools: [
          { tool: 'ext_0123456789ab_list_issues', policy: 'allow' },
          { tool: 'ext_0123456789ab_create_issue', policy: 'confirm' },
          { tool: 'ext_0123456789ab_get_project', policy: 'allow' },
        ],
        version: 7,
      }),
    )
  })

  test('level 4 is offered where the API allows it, and explained', async () => {
    setup(tools())
    await renderApp(`/admin/agents/${AGENT_ID}`)
    const levels = await screen.findByRole('group', { name: 'Autonomiestufe' })
    expect(
      within(levels).getByRole('radio', { name: /Stufe 4: nach außen handeln/ }),
    ).toBeInTheDocument()
    expect(within(levels).getByText(/schreibende Werkzeuge externer Server/)).toBeVisible()
  })

  test('without the right to give it, level 4 is not offered', async () => {
    setup(tools({ max_level: 2 }))
    await renderApp(`/admin/agents/${AGENT_ID}`)
    const levels = await screen.findByRole('group', { name: 'Autonomiestufe' })
    expect(within(levels).queryByRole('radio', { name: /Stufe 4/ })).not.toBeInTheDocument()
    expect(within(levels).getByText('Höhere Stufen vergibt nur ein Admin.')).toBeVisible()
  })
})
