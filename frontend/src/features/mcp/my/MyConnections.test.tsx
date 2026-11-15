import { screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import type { Permission } from '@/lib/api'
import { makeMe, mockApi, page } from '@/test/api'
import { makeConnector, makePersonalServer } from '@/test/mcp'
import { renderApp } from '@/test/render'
import { sendBrowserTo } from '../browser'

vi.mock('../browser', () => ({ sendBrowserTo: vi.fn() }))

const CLIENT = '00000000-0000-7000-8000-00000000cc02'
const GITLAB = '00000000-0000-7000-8000-00000000c5e4'
const WIKI = '00000000-0000-7000-8000-00000000c5e5'
const JIRA = '00000000-0000-7000-8000-00000000c5e6'

const shell = (permissions: Permission[]) => ({
  'GET /api/auth/me': makeMe(permissions),
  'GET /api/spaces': page([]),
  'GET /api/approvals': page([]),
})

beforeEach(() => vi.mocked(sendBrowserTo).mockClear())

describe('my connections', () => {
  test('without AI: no entry in the sidebar, the page is not found, nothing is asked', async () => {
    const api = mockApi(shell(['directory.read']))
    await renderApp('/my-connections')
    expect(await screen.findByRole('heading', { name: 'Seite nicht gefunden' })).toBeVisible()
    expect(screen.queryByRole('link', { name: 'Meine Verbindungen' })).not.toBeInTheDocument()
    expect(api.calls.filter((c) => c.path.startsWith('/api/ai'))).toEqual([])
  })

  test('each server that acts in my name: connected, or how to connect it', async () => {
    const mine = makeConnector({
      name: 'Wiki',
      scope: 'personal',
      auth_kind: 'bearer',
      mcp_server_id: WIKI,
    })
    const made = makeConnector({
      id: '00000000-0000-7000-8000-00000000cd09',
      name: 'GitLab',
      scope: 'personal',
      auth_kind: 'oauth',
      has_secret: false,
      oauth_client_id: CLIENT,
      mcp_server_id: GITLAB,
    })
    const api = mockApi({
      ...shell(['ai.use']),
      'GET /api/ai/my-mcp-servers': page([
        makePersonalServer({ id: GITLAB, name: 'GitLab', oauth_client_id: CLIENT }),
        makePersonalServer({ id: WIKI, name: 'Wiki', connected: true }),
        makePersonalServer({ id: JIRA, name: 'Jira' }),
      ]),
      'GET /api/ai/my-connectors': page([mine]),
      'POST /api/ai/my-connectors': { status: 201, body: made },
      [`POST /api/ai/my-connectors/${made.id}/authorize`]: {
        authorization_url: 'https://gitlab.com/oauth/authorize?state=abc',
      },
    })
    const { user } = await renderApp('/my-connections')
    expect(await screen.findByRole('heading', { name: 'Meine Verbindungen' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Meine Verbindungen' })).toBeInTheDocument()

    const wiki = screen.getByRole('article', { name: 'Wiki' })
    expect(within(wiki).getByText('Schlüssel hinterlegt (verschlüsselt)')).toBeInTheDocument()
    expect(within(wiki).getByRole('button', { name: 'Schlüssel ersetzen' })).toBeVisible()

    const jira = screen.getByRole('article', { name: 'Jira' })
    expect(within(jira).getByText('Nicht verbunden')).toBeInTheDocument()
    await user.click(within(jira).getByRole('button', { name: 'Token hinterlegen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Eigenes Token für Jira' })
    // One's own key is a value; an environment variable is the operator's.
    expect(within(dialog).queryByLabelText('Umgebungsvariable')).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Abbrechen' }))

    const gitlab = screen.getByRole('article', { name: 'GitLab' })
    await user.click(within(gitlab).getByRole('button', { name: 'Mit GitLab verbinden' }))
    await waitFor(() =>
      expect(sendBrowserTo).toHaveBeenCalledWith('https://gitlab.com/oauth/authorize?state=abc'),
    )
    expect(api.find('POST', '/api/ai/my-connectors')[0]!.body).toEqual({
      name: 'GitLab',
      auth_kind: 'oauth',
      oauth_client_id: CLIENT,
      mcp_server_id: GITLAB,
    })
  })

  test('a token of mine for a server goes with the server', async () => {
    const api = mockApi({
      ...shell(['ai.use']),
      'GET /api/ai/my-mcp-servers': page([makePersonalServer({ id: JIRA, name: 'Jira' })]),
      'GET /api/ai/my-connectors': page([]),
      'POST /api/ai/my-connectors': {
        status: 201,
        body: makeConnector({ scope: 'personal', mcp_server_id: JIRA, name: 'Jira' }),
      },
    })
    const { user } = await renderApp('/my-connections')
    await user.click(await screen.findByRole('button', { name: 'Token hinterlegen' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByLabelText('Name')).toHaveValue('Jira')
    await user.type(within(dialog).getByLabelText('Schlüssel oder Token'), 'pat-1')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(api.find('POST', '/api/ai/my-connectors')).toHaveLength(1))
    expect(api.find('POST', '/api/ai/my-connectors')[0]!.body).toEqual({
      name: 'Jira',
      auth_kind: 'bearer',
      header_name: null,
      oauth_client_id: null,
      mcp_server_id: JIRA,
      secret: { value: 'pat-1' },
    })
  })

  test('no server asks for personal access: says so', async () => {
    mockApi({
      ...shell(['ai.use']),
      'GET /api/ai/my-mcp-servers': page([]),
      'GET /api/ai/my-connectors': page([]),
    })
    await renderApp('/my-connections')
    expect(await screen.findByText('Kein Server verlangt einen persönlichen Zugang.')).toBeVisible()
  })
})

describe('coming back from the provider', () => {
  test.each([
    ['connected', 'Verbunden', 'status'],
    ['denied', 'Nicht verbunden', 'alert'],
    ['failed', 'Verbinden fehlgeschlagen', 'alert'],
    ['invalid', 'Anmeldung abgelaufen', 'alert'],
    ['whatever', 'Verbinden fehlgeschlagen', 'alert'],
  ])('status=%s says so in words', async (status, title, role) => {
    mockApi(shell(['ai.use', 'ai.manage']))
    await renderApp(`/ai/oauth/done?status=${status}`)
    expect(await screen.findByRole('heading', { name: title })).toBeVisible()
    expect(screen.getAllByRole(role).length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'Zu meinen Verbindungen' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Zu den Konnektoren' })).toBeVisible()
  })

  test('only the links one may follow', async () => {
    mockApi(shell(['ai.use']))
    await renderApp('/ai/oauth/done?status=connected')
    expect(await screen.findByRole('link', { name: 'Zu meinen Verbindungen' })).toBeVisible()
    expect(screen.queryByRole('link', { name: 'Zu den Konnektoren' })).not.toBeInTheDocument()
  })
})
