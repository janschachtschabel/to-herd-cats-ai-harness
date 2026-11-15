import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { apiError, makeMe, mockApi, page } from '@/test/api'
import { makeEntry, makeServer } from '@/test/mcp'
import { renderApp } from '@/test/render'

const SRV = '00000000-0000-7000-8000-00000000c5e3'

const shell = {
  'GET /api/auth/me': makeMe(['ai.manage']),
  'GET /api/spaces': page([]),
}

const github = makeEntry({
  id: 'github',
  name: 'GitHub',
  description: { de: 'Der MCP-Server von GitHub.', en: "GitHub's MCP server." },
  url: 'https://api.githubcopilot.com/mcp/',
  base_url: null,
  connector_scopes: ['shared', 'personal'],
  auth: [
    {
      kind: 'bearer',
      note: { de: 'Ein persönliches Zugriffstoken.', en: 'A personal access token.' },
    },
  ],
})

describe('the catalogue', () => {
  test('lists the templates; broken operator files are named without their content', async () => {
    mockApi({
      ...shell,
      'GET /api/ai/mcp-catalog': page([github, makeEntry()]),
      'GET /api/ai/mcp-catalog/problems': page([
        { source: 'operator', file: 'jira.yaml', reason: 'auth.0.kind: unknown value' },
      ]),
    })
    await renderApp('/admin/ai/catalog')
    const gitlab = await screen.findByRole('article', { name: 'GitLab' })
    expect(within(gitlab).getByText('Der MCP-Server von GitLab.')).toBeInTheDocument()
    expect(
      within(gitlab).getByText('Schlägt die Einstufung für 2 Werkzeuge vor (1 schreibend).'),
    ).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'GitHub' })).toBeInTheDocument()
    const problems = screen.getByRole('region', { name: 'Katalogdateien mit Fehlern' })
    expect(within(problems).getByText('jira.yaml')).toBeInTheDocument()
    expect(within(problems).getByText('(Betrieb)')).toBeInTheDocument()
    expect(within(problems).getByText('auth.0.kind: unknown value')).toBeInTheDocument()
  })

  test('no problems: no problem box', async () => {
    mockApi({
      ...shell,
      'GET /api/ai/mcp-catalog': page([github]),
      'GET /api/ai/mcp-catalog/problems': page([]),
    })
    await renderApp('/admin/ai/catalog')
    await screen.findByRole('article', { name: 'GitHub' })
    expect(screen.queryByText('Katalogdateien mit Fehlern')).not.toBeInTheDocument()
  })

  test('GitLab on an own instance with OAuth: one step, then the server’s page', async () => {
    const server = makeServer({
      id: SRV,
      name: 'GitLab',
      url: 'https://gitlab.example.com/api/v4/mcp',
      catalog_id: 'gitlab',
      connector_scope: 'personal',
    })
    const api = mockApi({
      ...shell,
      'GET /api/ai/mcp-catalog': page([makeEntry()]),
      'GET /api/ai/mcp-catalog/problems': page([]),
      'POST /api/ai/mcp-catalog/gitlab/install': {
        status: 201,
        body: {
          server: { ...server, refresh: { status: 'ok', new: 62, changed: 0, missing: 0 } },
          oauth_client_id: '00000000-0000-7000-8000-00000000cc09',
          connector_id: null,
        },
      },
      [`GET /api/ai/mcp-servers/${SRV}`]: server,
      [`GET /api/ai/mcp-servers/${SRV}/tools`]: page([]),
    })
    const { user, router } = await renderApp('/admin/ai/catalog')
    await user.click(await screen.findByRole('button', { name: 'GitLab einrichten' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Für eine eigene Instanz deren Adresse.')).toBeInTheDocument()
    const base = within(dialog).getByLabelText('Adresse der Instanz')
    expect(base).toHaveValue('https://gitlab.com')
    await user.clear(base)
    await user.type(base, 'https://gitlab.example.com')
    // Personal is the first scope the entry names; OAuth its first sign-in.
    expect(within(dialog).getByLabelText(/Persönlicher Zugang/)).toBeChecked()
    expect(within(dialog).getByText('In GitLab eine Anwendung anlegen.')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Einrichten' }))
    expect(await within(dialog).findByText('Bitte ausfüllen.')).toBeInTheDocument()
    await user.type(within(dialog).getByLabelText('Client-ID'), 'app-42')
    await user.click(within(dialog).getByRole('button', { name: 'Einrichten' }))
    await waitFor(() =>
      expect(api.find('POST', '/api/ai/mcp-catalog/gitlab/install')).toHaveLength(1),
    )
    expect(api.find('POST', '/api/ai/mcp-catalog/gitlab/install')[0]!.body).toEqual({
      connector_scope: 'personal',
      auth_kind: 'oauth',
      name: 'GitLab',
      base_url: 'https://gitlab.example.com',
      secret: null,
      client_id: 'app-42',
      client_secret: null,
      data_location: 'external',
      enabled: true,
    })
    await waitFor(() => expect(router.state.location.pathname).toBe(`/admin/ai/mcp-servers/${SRV}`))
  })

  test('a shared token goes with the installation; a refusal is put into words', async () => {
    const api = mockApi({
      ...shell,
      'GET /api/ai/mcp-catalog': page([github]),
      'GET /api/ai/mcp-catalog/problems': page([]),
      'POST /api/ai/mcp-catalog/github/install': apiError(409, 'mcp_server.name_taken'),
    })
    const { user } = await renderApp('/admin/ai/catalog')
    await user.click(await screen.findByRole('button', { name: 'GitHub einrichten' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).queryByLabelText('Adresse der Instanz')).not.toBeInTheDocument()
    expect(within(dialog).getByLabelText(/Geteilter Zugang/)).toBeChecked()
    await user.type(within(dialog).getByLabelText('Schlüssel oder Token'), 'ghp_x')
    await user.click(within(dialog).getByRole('button', { name: 'Einrichten' }))
    expect(await within(dialog).findByText('Diesen Namen trägt schon ein Server.')).toBeVisible()
    expect(api.find('POST', '/api/ai/mcp-catalog/github/install')[0]!.body).toMatchObject({
      connector_scope: 'shared',
      auth_kind: 'bearer',
      base_url: null,
      secret: { value: 'ghp_x' },
      client_id: null,
    })
  })
})
