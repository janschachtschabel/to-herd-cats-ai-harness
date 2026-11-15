import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Permission } from '@/lib/api'
import { apiError, makeMe, mockApi, page } from '@/test/api'
import { makeConnector, makeServer } from '@/test/mcp'
import { renderApp } from '@/test/render'

const AI_ADMIN: Permission[] = ['ai.manage', 'ai.use', 'directory.read']

const CONN = '00000000-0000-7000-8000-00000000c0c1'
const SRV = '00000000-0000-7000-8000-00000000c5e1'

const shell = (permissions: Permission[]) => ({
  'GET /api/auth/me': makeMe(permissions),
  'GET /api/spaces': page([]),
  'GET /api/approvals': page([]),
})

describe('external MCP servers', () => {
  test.each(['/admin/ai/mcp-servers', '/admin/ai/connectors', '/admin/ai/catalog'])(
    'without ai.manage: not found, no tab, no request (%s)',
    async (path) => {
      const api = mockApi(shell(['user.manage', 'ai.use']))
      await renderApp(path)
      expect(
        await screen.findByRole('heading', { name: 'Seite nicht gefunden' }),
      ).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: 'MCP-Server' })).not.toBeInTheDocument()
      expect(api.calls.filter((c) => /mcp|connectors|oauth-clients/.test(c.path))).toEqual([])
    },
  )

  test('each server in the list says where its data goes, its access and if it is on', async () => {
    mockApi({
      ...shell(AI_ADMIN),
      'GET /api/ai/mcp-servers': page([
        makeServer({ id: SRV, name: 'Wetter', enabled: false, connector_scope: 'none' }),
      ]),
    })
    await renderApp('/admin/ai/mcp-servers')
    const row = await screen.findByRole('link', { name: /Wetter/ })
    expect(within(row).getByText('Datenort: Extern')).toBeInTheDocument()
    expect(within(row).getByText('Ohne Zugang')).toBeInTheDocument()
    expect(within(row).getByText('Ausgeschaltet')).toBeInTheDocument()
  })

  test('no server yet: says so; added by its address it opens with its tools read', async () => {
    const shared = makeConnector({ id: CONN, name: 'GitHub-Token' })
    const created = makeServer({ id: SRV, name: 'GitHub', connector_id: CONN })
    const api = mockApi({
      ...shell(AI_ADMIN),
      'GET /api/ai/mcp-servers': page([]),
      'GET /api/ai/connectors': page([shared]),
      'POST /api/ai/mcp-servers': {
        status: 201,
        body: { ...created, refresh: { status: 'ok', new: 3, changed: 0, missing: 0 } },
      },
      [`GET /api/ai/mcp-servers/${SRV}`]: created,
      [`GET /api/ai/connectors/${CONN}`]: shared,
      [`GET /api/ai/mcp-servers/${SRV}/tools`]: page([]),
    })
    const { user, router } = await renderApp('/admin/ai/mcp-servers')
    expect(await screen.findByText('Noch kein MCP-Server eingerichtet.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'MCP-Server' })).toHaveAttribute(
      'data-status',
      'active',
    )

    await user.click(screen.getAllByRole('button', { name: 'Server hinzufügen' })[0]!)
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Name'), 'GitHub')
    await user.type(within(dialog).getByLabelText('Adresse'), 'https://api.githubcopilot.com/mcp/')
    await user.selectOptions(within(dialog).getByLabelText('Zugang'), 'shared')
    // A shared access needs its connector.
    await user.click(within(dialog).getByRole('button', { name: 'Hinzufügen und einlesen' }))
    expect(await within(dialog).findByText('Bitte ausfüllen.')).toBeInTheDocument()
    expect(api.find('POST', '/api/ai/mcp-servers')).toHaveLength(0)

    await user.selectOptions(await within(dialog).findByLabelText('Geteilter Konnektor'), CONN)
    await user.click(within(dialog).getByRole('button', { name: 'Hinzufügen und einlesen' }))
    await waitFor(() => expect(api.find('POST', '/api/ai/mcp-servers')).toHaveLength(1))
    expect(api.find('POST', '/api/ai/mcp-servers')[0]!.body).toEqual({
      name: 'GitHub',
      url: 'https://api.githubcopilot.com/mcp/',
      data_location: 'external',
      enabled: true,
      connector_scope: 'shared',
      connector_id: CONN,
      oauth_client_id: null,
    })
    await waitFor(() => expect(router.state.location.pathname).toBe(`/admin/ai/mcp-servers/${SRV}`))
    expect(await screen.findByRole('heading', { name: 'GitHub' })).toBeInTheDocument()
    expect(await screen.findByText('Schlüssel hinterlegt (verschlüsselt)')).toBeInTheDocument()
  })

  test('a server whose tools could not be read says why, in words', async () => {
    const server = makeServer({ id: 'srv-2', connector_scope: 'none' })
    mockApi({
      ...shell(AI_ADMIN),
      'GET /api/ai/mcp-servers/srv-2': server,
      'GET /api/ai/mcp-servers/srv-2/tools': page([]),
    })
    await renderApp('/admin/ai/mcp-servers/srv-2?read=blocked')
    expect(await screen.findByText(/Gesperrt: Die Adresse ist nicht erlaubt/)).toBeInTheDocument()
    expect(screen.getByText(/Der Server hat \(noch\) keine Werkzeuge/)).toBeInTheDocument()
  })

  test('test, refresh and switching off answer in words; a stale version asks to reload', async () => {
    const server = makeServer({ id: 'srv-3', connector_scope: 'none', version: 2 })
    const api = mockApi({
      ...shell(AI_ADMIN),
      'GET /api/ai/mcp-servers': page([server]),
      'GET /api/ai/mcp-servers/srv-3': server,
      'GET /api/ai/mcp-servers/srv-3/tools': page([]),
      'POST /api/ai/mcp-servers/srv-3/test': { status: 'ok', tools: 12, duration_ms: 340 },
      'POST /api/ai/mcp-servers/srv-3/refresh': { status: 'ok', new: 2, changed: 1, missing: 0 },
      'PATCH /api/ai/mcp-servers/srv-3': apiError(409, 'mcp_server.version_conflict'),
    })
    const { user } = await renderApp('/admin/ai/mcp-servers')
    await user.click(await screen.findByRole('link', { name: /GitHub/ }))

    await user.click(await screen.findByRole('button', { name: 'Verbindung testen' }))
    expect(await screen.findByText('Verbunden: 12 Werkzeuge, 340 ms.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Werkzeuge neu einlesen' }))
    expect(await screen.findByText('2 neue Werkzeuge · 1 geändertes Werkzeug')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Ausschalten' }))
    await waitFor(() => expect(api.find('PATCH', '/api/ai/mcp-servers/srv-3')).toHaveLength(1))
    expect(api.find('PATCH', '/api/ai/mcp-servers/srv-3')[0]!.body).toEqual({
      enabled: false,
      version: 2,
    })
    expect(await screen.findByText(/inzwischen geändert/)).toBeInTheDocument()
  })

  test('changing the address warns that every approval is withdrawn', async () => {
    const server = makeServer({ id: 'srv-4', connector_scope: 'none' })
    mockApi({
      ...shell(AI_ADMIN),
      'GET /api/ai/mcp-servers/srv-4': server,
      'GET /api/ai/mcp-servers/srv-4/tools': page([]),
    })
    const { user } = await renderApp('/admin/ai/mcp-servers/srv-4')
    await user.click(await screen.findByRole('button', { name: 'Bearbeiten' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).queryByText(/zieht alle Freigaben zurück/)).not.toBeInTheDocument()
    const url = within(dialog).getByLabelText('Adresse')
    await user.clear(url)
    await user.type(url, 'https://mcp.example.com/mcp')
    expect(within(dialog).getByText(/zieht alle Freigaben zurück/)).toBeInTheDocument()
  })

  test('a new origin disconnects personal access; a shared connector is kept only on request', async () => {
    const server = makeServer({ id: 'srv-5', connector_scope: 'shared', connector_id: CONN })
    const api = mockApi({
      ...shell(AI_ADMIN),
      'GET /api/ai/mcp-servers/srv-5': server,
      'GET /api/ai/mcp-servers/srv-5/tools': page([]),
      'GET /api/ai/connectors': page([makeConnector({ id: CONN })]),
      'GET /api/ai/oauth-clients': page([]),
      'PATCH /api/ai/mcp-servers/srv-5': { ...server, version: 2 },
    })
    const { user } = await renderApp('/admin/ai/mcp-servers/srv-5')
    await user.click(await screen.findByRole('button', { name: 'Bearbeiten' }))
    const dialog = await screen.findByRole('dialog')
    const url = within(dialog).getByLabelText('Adresse')
    await user.clear(url)
    await user.type(url, 'https://api.githubcopilot.com/other/') // the path only
    expect(within(dialog).queryByText(/trennt jede eigene Verbindung/)).not.toBeInTheDocument()
    await user.clear(url)
    await user.type(url, 'https://mcp.example.com/mcp')
    expect(within(dialog).getByText(/trennt jede eigene Verbindung/)).toBeInTheDocument()
    await user.click(within(dialog).getByLabelText(/Geteilten Konnektor behalten/))
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(api.find('PATCH', '/api/ai/mcp-servers/srv-5')).toHaveLength(1))
    expect(api.find('PATCH', '/api/ai/mcp-servers/srv-5')[0]!.body).toMatchObject({
      url: 'https://mcp.example.com/mcp',
      keep_shared_connector: true,
    })
  })
})
