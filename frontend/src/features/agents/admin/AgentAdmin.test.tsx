import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Schemas } from '@/lib/api'
import { apiError, makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'
import { makeSkill } from '@/test/skills'

type Agent = Schemas['AgentOut']
type Tools = Schemas['AgentToolsOut']

const me = makeMe(['agent.manage', 'ai.manage', 'skill.manage', 'directory.read'])
const AGENT_ID = '00000000-0000-7000-8000-0000000000a1'

const agent: Agent = {
  id: AGENT_ID,
  name: 'Hilda',
  intro: 'Hilft beim Handbuch.',
  instructions: 'Antworte kurz.',
  connection_id: '00000000-0000-7000-8000-00000000c001',
  model: 'gpt-6-luna',
  responsible_user_id: me.user.id,
  responsible_name: 'Mia Muster',
  status: 'active',
  max_steps: 25,
  max_runtime_seconds: 600,
  level: 2,
  version: 4,
  created_at: '2026-11-13T08:00:00Z',
  updated_at: '2026-11-13T08:00:00Z',
}

function tools(overrides: Partial<Tools> = {}): Tools {
  return {
    agent_id: AGENT_ID,
    level: 2,
    max_level: 3,
    version: 4,
    tools: [
      {
        name: 'search',
        level: 1,
        effect: 'read',
        default: 'allow',
        entry: null,
        effective: 'allow',
      },
      {
        name: 'propose_page_change',
        level: 2,
        effect: 'propose',
        default: 'allow',
        entry: 'confirm',
        effective: 'confirm',
      },
      {
        name: 'update_page',
        level: 3,
        effect: 'write',
        default: 'block',
        entry: null,
        effective: 'block',
      },
    ],
    ...overrides,
  }
}

function base(extra: Record<string, unknown> = {}) {
  return {
    'GET /api/auth/me': me,
    'GET /api/spaces': page([]),
    'GET /api/agents/:id': agent,
    'GET /api/agents/:id/tools': tools(),
    'GET /api/agents/:id/spaces': page([
      { id: 'space-1', name: 'Handbuch', kind: 'team', role: 'editor' },
    ]),
    'GET /api/agents/:id/skills': { version: 4, skills: [] },
    ...extra,
  }
}

describe('agent administration: level, tools, spaces, skills', () => {
  test('the level in words; level 3 is offered only when the API allows it', async () => {
    const api = mockApi(
      base({
        'PATCH /api/agents/:id': apiError(403, 'agent.level_denied'),
      }),
    )
    const { user } = await renderApp(`/admin/agents/${AGENT_ID}`)
    const levels = await screen.findByRole('group', { name: 'Autonomiestufe' })
    expect(within(levels).getByRole('radio', { name: /Stufe 2: vorschlagen/ })).toBeChecked()
    expect(within(levels).getByText(/schlägt Änderungen an Seiten vor/)).toBeInTheDocument()
    await user.click(within(levels).getByRole('radio', { name: /Stufe 3: intern schreiben/ }))
    await user.click(within(levels).getByRole('button', { name: 'Stufe speichern' }))
    await waitFor(() =>
      expect(api.find('PATCH', `/api/agents/${AGENT_ID}`)[0]?.body).toEqual({
        level: 3,
        version: 4,
      }),
    )
    expect(
      await within(levels).findByText(/Stufe 3 vergibt nur ein Admin oder wer jeden Bereich/),
    ).toBeInTheDocument()
  })

  test('without the right to give level 3 it is not offered, and says why', async () => {
    mockApi(base({ 'GET /api/agents/:id/tools': tools({ max_level: 2 }) }))
    await renderApp(`/admin/agents/${AGENT_ID}`)
    const levels = await screen.findByRole('group', { name: 'Autonomiestufe' })
    expect(within(levels).queryByRole('radio', { name: /Stufe 3/ })).not.toBeInTheDocument()
    expect(within(levels).getByText(/Stufe 3 vergibt nur/)).toBeInTheDocument()
  })

  test('tools: the effective grant, tightening only, a tool above the level not available', async () => {
    const api = mockApi(
      base({
        'PUT /api/agents/:id/tools': () => ({
          ...tools(),
          version: 5,
          tools: tools().tools.map((t) =>
            t.name === 'search' ? { ...t, entry: 'block', effective: 'block' } : t,
          ),
        }),
      }),
    )
    const { user } = await renderApp(`/admin/agents/${AGENT_ID}`)
    const table = await screen.findByRole('table', { name: 'Werkzeuge des Agenten' })
    const search = within(table).getByRole('row', { name: /Suchen/ })
    expect(within(search).getByText('Erlaubt')).toBeInTheDocument()
    const choice = within(search).getByRole('combobox', { name: 'Freigabe für Suchen' })
    expect(
      within(choice)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Wie die Stufe (erlaubt)', 'Nur nach Freigabe', 'Gesperrt'])
    const update = within(table).getByRole('row', { name: /Seite direkt ändern/ })
    expect(within(update).getByText('Nicht verfügbar: braucht Stufe 3')).toBeInTheDocument()
    expect(within(update).queryByRole('combobox')).not.toBeInTheDocument()
    await user.selectOptions(choice, 'Gesperrt')
    await user.click(screen.getByRole('button', { name: 'Freigaben speichern' }))
    await waitFor(() =>
      expect(api.find('PUT', `/api/agents/${AGENT_ID}/tools`)[0]?.body).toEqual({
        tools: [
          { tool: 'search', policy: 'block' },
          { tool: 'propose_page_change', policy: 'confirm' },
        ],
        version: 4,
      }),
    )
  })

  test('a stale version on the tools offers to reload', async () => {
    mockApi(base({ 'PUT /api/agents/:id/tools': apiError(409, 'agent.version_conflict') }))
    const { user } = await renderApp(`/admin/agents/${AGENT_ID}`)
    await screen.findByRole('table', { name: 'Werkzeuge des Agenten' })
    await user.click(screen.getByRole('button', { name: 'Freigaben speichern' }))
    expect(
      await screen.findByRole('button', { name: 'Aktuelle Fassung laden' }),
    ).toBeInTheDocument()
  })

  test('its spaces with the role there', async () => {
    mockApi(base())
    await renderApp(`/admin/agents/${AGENT_ID}`)
    const spaces = await screen.findByRole('list', { name: 'Bereiche des Agenten' })
    expect(within(spaces).getByRole('link', { name: 'Handbuch' })).toBeInTheDocument()
    expect(within(spaces).getByText('Autor')).toBeInTheDocument()
  })

  test('skills: assign from the offered ones; one not available says why', async () => {
    const archived = makeSkill({ name: 'alt-skill', state: 'archived' })
    const offered = makeSkill({ name: 'protokoll', description: 'Schreibt Protokolle.' })
    const api = mockApi(
      base({
        'GET /api/agents/:id/skills': {
          version: 4,
          skills: [{ ...archived, available: false }],
        },
        'GET /api/skills': page([offered]),
        'PUT /api/agents/:id/skills': {
          version: 5,
          skills: [
            { ...archived, available: false },
            { ...offered, available: true },
          ],
        },
      }),
    )
    const { user } = await renderApp(`/admin/agents/${AGENT_ID}`)
    const skills = await screen.findByRole('list', { name: 'Skills des Agenten' })
    expect(within(skills).getByText('alt-skill')).toBeInTheDocument()
    expect(
      within(skills).getByText(/Nicht verfügbar: Der Skill ist archiviert/),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Skills zuweisen' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(await within(dialog).findByRole('checkbox', { name: /protokoll/ }))
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() =>
      expect(api.find('PUT', `/api/agents/${AGENT_ID}/skills`)[0]?.body).toEqual({
        skill_ids: [archived.id, offered.id],
        version: 4,
      }),
    )
    expect(api.find('GET', '/api/skills')[0]?.query.get('state')).toBe('active')
  })
})
