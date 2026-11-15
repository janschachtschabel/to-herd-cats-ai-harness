import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Schemas } from '@/lib/api'
import { apiError, makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'
import { makeAdminToken, makeCall } from '@/test/tokens'

type Settings = Schemas['McpSettingsOut']

const shell = {
  'GET /api/auth/me': makeMe(['ai.manage']),
  'GET /api/spaces': page([]),
}

describe('MCP administration', () => {
  test('only with ai.manage: the tab and the page', async () => {
    mockApi({ ...shell, 'GET /api/auth/me': makeMe(['agent.manage']) })
    const { router } = await renderApp('/admin/agents')
    await router.navigate({ to: '/admin/ai/mcp' })
    expect(await screen.findByText('Seite nicht gefunden')).toBeInTheDocument()
  })

  test('switches access on with a data location, at the read version', async () => {
    let settings: Settings = { enabled: false, data_location: 'external', version: 3 }
    const api = mockApi({
      ...shell,
      'GET /api/ai/mcp': () => settings,
      'PUT /api/ai/mcp': (call) => {
        settings = { ...(call.body as Settings), version: settings.version + 1 }
        return settings
      },
      'GET /api/ai/mcp/tokens': page([]),
    })
    const { user } = await renderApp('/admin/ai')
    await user.click(await screen.findByRole('link', { name: 'MCP-Zugang' }))
    const access = await screen.findByRole('checkbox', { name: /Zugangstoken erlauben/ })
    expect(access).not.toBeChecked()
    expect(screen.getByText(/Niemand kann Zugangstoken anlegen/)).toBeInTheDocument()
    await user.click(access)
    await user.selectOptions(screen.getByLabelText('Datenort der Clients'), 'eu')
    await user.click(screen.getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(api.find('PUT', '/api/ai/mcp')).toHaveLength(1))
    expect(api.find('PUT', '/api/ai/mcp')[0]!.body).toEqual({
      enabled: true,
      data_location: 'eu',
      version: 3,
    })
    expect(await screen.findByRole('status')).toHaveTextContent(/Eingeschaltet/)
  })

  test('a stale version asks to reload; the choice made is kept and saved anew', async () => {
    let version = 1
    const api = mockApi({
      ...shell,
      'GET /api/ai/mcp': () => ({ enabled: true, data_location: 'external', version }),
      'PUT /api/ai/mcp': (call) =>
        (call.body as Settings).version === version
          ? { ...(call.body as Settings), version: version + 1 }
          : apiError(409, 'mcp.settings_version_conflict', 'stale', { current_version: version }),
      'GET /api/ai/mcp/tokens': page([]),
    })
    const { user } = await renderApp('/admin/ai/mcp')
    await user.click(await screen.findByRole('checkbox', { name: /Zugangstoken erlauben/ }))
    version = 2 // someone else saved meanwhile
    await user.click(screen.getByRole('button', { name: 'Speichern' }))
    expect(await screen.findByText(/inzwischen geändert/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Aktuelle Fassung laden' }))
    await waitFor(() => expect(screen.queryByText(/inzwischen geändert/)).not.toBeInTheDocument())
    expect(screen.getByRole('checkbox', { name: /Zugangstoken erlauben/ })).not.toBeChecked()
    await user.click(screen.getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(api.find('PUT', '/api/ai/mcp')).toHaveLength(2))
    expect(api.find('PUT', '/api/ai/mcp')[1]!.body).toEqual({
      enabled: false,
      data_location: 'external',
      version: 2,
    })
  })

  test('lists every token of the organisation with its owner; revokes and shows calls', async () => {
    const person = makeAdminToken({ name: 'Laptop', user: { id: 'u1', name: 'Lea Löwe' } })
    const agent = makeAdminToken({
      name: 'Pipeline',
      kind: 'agent',
      agent_id: 'a1',
      agent: { id: 'a1', name: 'Codi' },
      user: { id: 'u2', name: 'Ben Bauer' },
      mode: 'write',
    })
    const api = mockApi({
      ...shell,
      'GET /api/ai/mcp': { enabled: true, data_location: 'external', version: 1 },
      'GET /api/ai/mcp/tokens': page([person, agent]),
      [`GET /api/ai/mcp/tokens/${agent.id}/calls`]: page([makeCall({ tool: 'claim_ticket' })]),
      [`DELETE /api/ai/mcp/tokens/${person.id}`]: { status: 204 },
    })
    const { user } = await renderApp('/admin/ai/mcp')
    const laptop = await screen.findByRole('article', { name: 'Laptop' })
    expect(within(laptop).getByText('Persönliches Token von Lea Löwe')).toBeInTheDocument()
    const pipeline = screen.getByRole('article', { name: 'Pipeline' })
    expect(
      within(pipeline).getByText('Token des Agenten Codi (verantwortlich: Ben Bauer)'),
    ).toBeInTheDocument()
    await user.click(within(pipeline).getByRole('button', { name: 'Aufrufe von Pipeline' }))
    expect(await screen.findByText('claim_ticket')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    await user.click(within(laptop).getByRole('button', { name: 'Laptop widerrufen' }))
    const confirm = await screen.findByRole('dialog', { name: 'Token widerrufen?' })
    await user.click(within(confirm).getByRole('button', { name: 'Widerrufen' }))
    await waitFor(() =>
      expect(api.find('DELETE', `/api/ai/mcp/tokens/${person.id}`)).toHaveLength(1),
    )
  })
})
