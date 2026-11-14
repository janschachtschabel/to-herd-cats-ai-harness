import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Permission, Schemas } from '@/lib/api'
import { apiError, makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

type Connection = Schemas['ConnectionOut']

const AI_ADMIN: Permission[] = ['ai.manage', 'agent.manage', 'directory.read', 'user.manage']

function makeConnection(overrides: Partial<Connection> = {}): Connection {
  return {
    id: '00000000-0000-7000-8000-00000000c001',
    name: 'Stub',
    kind: 'local',
    base_url: 'http://127.0.0.1:8099/v1',
    secret: { set: true, kind: 'enc' },
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
    version: 3,
    created_at: '2026-11-13T08:00:00Z',
    updated_at: '2026-11-13T08:00:00Z',
    ...overrides,
  }
}

const shell = (permissions: Permission[]) => ({
  'GET /api/auth/me': makeMe(permissions),
  'GET /api/spaces': page([]),
})

describe('ai administration', () => {
  test.each(['/admin/ai', '/admin/ai/assignments', '/admin/ai/usage', '/admin/agents'])(
    'without ai.manage / agent.manage: no menu entry, not found, no AI request (%s)',
    async (path) => {
      const api = mockApi(shell(['user.manage', 'ai.use']))
      await renderApp(path)
      expect(
        await screen.findByRole('heading', { name: 'Seite nicht gefunden' }),
      ).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: 'KI' })).not.toBeInTheDocument()
      expect(screen.queryByRole('link', { name: 'Agenten' })).not.toBeInTheDocument()
      expect(
        api.calls.filter((c) => c.path.startsWith('/api/ai') || c.path.startsWith('/api/agents')),
      ).toEqual([])
    },
  )

  test('no connection yet: says so, and the admin sets one up with a key never shown again', async () => {
    const stored: Connection[] = []
    const api = mockApi({
      ...shell(AI_ADMIN),
      'GET /api/ai/connections': () => page(stored),
      'POST /api/ai/connections': (call) => {
        const body = call.body as Schemas['ConnectionCreate']
        const created = makeConnection({
          name: body.name,
          kind: body.kind ?? 'openai',
          models: body.models ?? [],
        })
        stored.push(created)
        return { status: 201, body: created }
      },
    })
    const { user, queryClient } = await renderApp('/admin/ai')
    expect(await screen.findByText(/Noch keine Verbindung eingerichtet/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'KI' })).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: 'Verbindung einrichten' })[0]!)
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Name'), 'Stub')
    await user.selectOptions(within(dialog).getByLabelText('Art'), 'Lokal')
    await user.type(
      within(dialog).getByLabelText('Adresse (Basis-URL)'),
      'http://127.0.0.1:8099/v1',
    )
    const key = within(dialog).getByLabelText('Schlüssel (wird verschlüsselt gespeichert)')
    expect(key).toHaveAttribute('type', 'password')
    await user.type(key, 'sk-secret-123')
    await user.type(within(dialog).getByLabelText('Modelle'), 'gpt-6-luna\ngpt-6-luna-mini')
    await user.selectOptions(within(dialog).getByLabelText('Datenort'), 'Lokal')
    await user.click(within(dialog).getByRole('button', { name: 'Einrichten' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(api.find('POST', '/api/ai/connections')[0]?.body).toMatchObject({
      name: 'Stub',
      kind: 'local',
      base_url: 'http://127.0.0.1:8099/v1',
      secret: { value: 'sk-secret-123' },
      models: ['gpt-6-luna', 'gpt-6-luna-mini'],
      data_location: 'local',
      param_family: null,
    })
    const card = await screen.findByRole('article', { name: 'Stub' })
    expect(within(card).getByText('Verschlüsselt gespeichert')).toBeInTheDocument()
    expect(screen.queryByText(/sk-secret-123/)).not.toBeInTheDocument()
    // nor kept in memory with the finished mutation (TanStack keeps variables 5 min)
    await waitFor(() =>
      expect(
        JSON.stringify(
          queryClient
            .getMutationCache()
            .getAll()
            .map((m) => m.state.variables),
        ),
      ).not.toContain('sk-secret-123'),
    )
  })

  test('editing keeps the key unless a new one is given; a stale version says so', async () => {
    const connection = makeConnection()
    const api = mockApi({
      ...shell(AI_ADMIN),
      'GET /api/ai/connections': page([connection]),
      'GET /api/ai/connections/:id': { ...connection, version: 4 },
      'PATCH /api/ai/connections/:id': apiError(409, 'ai.connection_version_conflict'),
    })
    const { user } = await renderApp('/admin/ai')
    const card = await screen.findByRole('article', { name: 'Stub' })
    await user.click(within(card).getByRole('button', { name: 'Bearbeiten' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/Ein Schlüssel ist gespeichert/)).toBeInTheDocument()
    expect(within(dialog).getByLabelText('Beibehalten')).toBeChecked()
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    expect(await within(dialog).findByText(/inzwischen geändert/)).toBeInTheDocument()
    const body = api.find('PATCH', `/api/ai/connections/${connection.id}`)[0]?.body as object
    expect(body).not.toHaveProperty('secret')
    expect(body).toMatchObject({ version: 3, models: ['gpt-6-luna', 'gpt-6-luna-mini'] })

    await user.click(within(dialog).getByRole('button', { name: 'Aktuelle Fassung laden' }))
    await user.click(within(dialog).getByLabelText('Umgebungsvariable'))
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Umgebungsvariable' }),
      'HERD_AI_KEY',
    )
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() =>
      expect(api.find('PATCH', `/api/ai/connections/${connection.id}`)).toHaveLength(2),
    )
    expect(api.find('PATCH', `/api/ai/connections/${connection.id}`)[1]?.body).toMatchObject({
      secret: { env: 'HERD_AI_KEY' },
      version: 4,
    })
  })

  test('the test button words the state, never the provider text; switching off sends the version', async () => {
    const connection = makeConnection()
    const api = mockApi({
      ...shell(AI_ADMIN),
      'GET /api/ai/connections': page([connection]),
      'POST /api/ai/connections/:id/test': {
        status: 'unauthorized',
        model: 'gpt-6-luna',
        duration_ms: 12,
      },
      'PATCH /api/ai/connections/:id': { ...connection, enabled: false, version: 4 },
    })
    const { user } = await renderApp('/admin/ai')
    const card = await screen.findByRole('article', { name: 'Stub' })
    await user.click(within(card).getByRole('button', { name: 'Testen' }))
    expect(await within(card).findByRole('status')).toHaveTextContent(
      'Anbieter lehnt ab: Schlüssel ungültig (401).',
    )
    await user.click(within(card).getByRole('button', { name: 'Ausschalten' }))
    await waitFor(() =>
      expect(api.find('PATCH', `/api/ai/connections/${connection.id}`)[0]?.body).toEqual({
        enabled: false,
        version: 3,
      }),
    )
  })

  test('the standard assignment is saved with the shared version', async () => {
    const connection = makeConnection()
    const api = mockApi({
      ...shell(AI_ADMIN),
      'GET /api/ai/connections': page([connection]),
      'GET /api/ai/assignments': { default: null, version: 7 },
      'GET /api/ai/assignments/groups': page([]),
      'GET /api/ai/assignments/users': page([]),
      'PUT /api/ai/assignments/default': (call) => ({
        default: { ...(call.body as { target: object }).target, connection_name: 'Stub' },
        version: 8,
      }),
    })
    const { user } = await renderApp('/admin/ai/assignments')
    const section = await screen.findByRole('region', { name: 'Standard der Organisation' })
    await user.selectOptions(within(section).getByLabelText('Verbindung'), 'Stub')
    await user.selectOptions(within(section).getByLabelText('Modell'), 'gpt-6-luna-mini')
    await user.click(within(section).getByRole('button', { name: 'Speichern' }))
    expect(await within(section).findByText('Gespeichert.')).toBeInTheDocument()
    expect(api.find('PUT', '/api/ai/assignments/default')[0]?.body).toEqual({
      target: { connection_id: connection.id, model: 'gpt-6-luna-mini' },
      version: 7,
    })
  })

  test('usage per person over a period', async () => {
    const api = mockApi({
      ...shell(AI_ADMIN),
      'GET /api/ai/usage': (call) =>
        page(
          call.query.get('by') === 'user'
            ? [
                {
                  day: '2026-11-13',
                  key_id: 'u1',
                  name: 'Ben',
                  calls: 3,
                  tokens_in: 1200,
                  tokens_out: 300,
                  tokens_cached: 0,
                  cost: null,
                  unpriced_calls: 3,
                  duration_ms: 900,
                },
              ]
            : [],
        ),
    })
    const { user } = await renderApp('/admin/ai/usage')
    expect(await screen.findByText('Kein Verbrauch in diesem Zeitraum.')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Aufteilen nach'), 'Person')
    expect(await screen.findByRole('cell', { name: 'Ben' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '1.200' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'ohne Preis' })).toBeInTheDocument()
    const last = api.find('GET', '/api/ai/usage').at(-1)!
    expect(last.query.get('by')).toBe('user')
    expect(last.query.get('from')).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
})
