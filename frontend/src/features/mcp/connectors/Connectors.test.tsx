import { screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import type { Schemas } from '@/lib/api'
import { apiError, makeMe, mockApi, page } from '@/test/api'
import { makeClient, makeConnector } from '@/test/mcp'
import { renderApp } from '@/test/render'
import { sendBrowserTo } from '../browser'

vi.mock('../browser', () => ({ sendBrowserTo: vi.fn() }))

type Connector = Schemas['ConnectorOut']

const CLIENT = '00000000-0000-7000-8000-00000000cc01'

const shell = {
  'GET /api/auth/me': makeMe(['ai.manage']),
  'GET /api/spaces': page([]),
}

beforeEach(() => vi.mocked(sendBrowserTo).mockClear())

describe('shared connectors', () => {
  test('a key is only ever written: stored, named by kind, never shown', async () => {
    const stored: Connector[] = []
    const api = mockApi({
      ...shell,
      'GET /api/ai/connectors': () => page(stored),
      'GET /api/ai/oauth-clients': page([]),
      'POST /api/ai/connectors': (call) => {
        const body = call.body as Schemas['ConnectorCreate']
        const made = makeConnector({
          name: body.name,
          auth_kind: body.auth_kind,
          header_name: body.header_name ?? null,
        })
        stored.push(made)
        return { status: 201, body: made }
      },
    })
    const { user } = await renderApp('/admin/ai/connectors')
    expect(await screen.findByText('Noch kein geteilter Konnektor.')).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'Konnektor anlegen' })[0]!)
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Name'), 'Wetter-API')
    await user.selectOptions(within(dialog).getByLabelText('Art'), 'header')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    // The header's name and the key are required.
    expect(await within(dialog).findAllByText('Bitte ausfüllen.')).toHaveLength(2)

    await user.type(within(dialog).getByLabelText('Name der Kopfzeile'), 'X-Api-Key')
    const key = within(dialog).getByLabelText('Schlüssel oder Token')
    expect(key).toHaveAttribute('type', 'password')
    await user.type(key, 'geheim-123')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(api.find('POST', '/api/ai/connectors')).toHaveLength(1))
    expect(api.find('POST', '/api/ai/connectors')[0]!.body).toEqual({
      name: 'Wetter-API',
      auth_kind: 'header',
      header_name: 'X-Api-Key',
      oauth_client_id: null,
      mcp_server_id: null,
      secret: { value: 'geheim-123' },
    })
    const card = await screen.findByRole('article', { name: 'Wetter-API' })
    expect(within(card).getByText('Schlüssel hinterlegt (verschlüsselt)')).toBeInTheDocument()
    expect(within(card).getByText('X-Api-Key')).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent('geheim-123')
  })

  test('a new OAuth connector is connected at once: the browser goes to the provider', async () => {
    const client = makeClient({ id: CLIENT, name: 'GitLab-App' })
    const made = makeConnector({
      id: '00000000-0000-7000-8000-00000000cd01',
      name: 'GitLab',
      auth_kind: 'oauth',
      oauth_client_id: CLIENT,
      has_secret: false,
      secret_kind: null,
    })
    const api = mockApi({
      ...shell,
      'GET /api/ai/connectors': page([]),
      'GET /api/ai/oauth-clients': page([client]),
      'POST /api/ai/connectors': { status: 201, body: made },
      [`POST /api/ai/connectors/${made.id}/authorize`]: {
        authorization_url: 'https://gitlab.com/oauth/authorize?state=s',
      },
    })
    const { user } = await renderApp('/admin/ai/connectors')
    await user.click((await screen.findAllByRole('button', { name: 'Konnektor anlegen' }))[0]!)
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Name'), 'GitLab')
    await user.selectOptions(within(dialog).getByLabelText('Art'), 'oauth')
    expect(within(dialog).queryByLabelText('Schlüssel oder Token')).not.toBeInTheDocument()
    await user.selectOptions(await within(dialog).findByLabelText('OAuth-App'), CLIENT)
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen und verbinden' }))
    await waitFor(() =>
      expect(sendBrowserTo).toHaveBeenCalledWith('https://gitlab.com/oauth/authorize?state=s'),
    )
    expect(api.find('POST', '/api/ai/connectors')[0]!.body).toMatchObject({
      auth_kind: 'oauth',
      oauth_client_id: CLIENT,
    })
  })

  test('connected, reconnect and disconnect; an address that is not https is never opened', async () => {
    const connector = makeConnector({
      id: '00000000-0000-7000-8000-00000000cd02',
      name: 'GitHub',
      auth_kind: 'oauth',
      oauth_client_id: CLIENT,
      has_secret: true,
      version: 4,
    })
    const api = mockApi({
      ...shell,
      'GET /api/ai/connectors': page([connector]),
      'GET /api/ai/oauth-clients': page([]),
      [`POST /api/ai/connectors/${connector.id}/authorize`]: {
        authorization_url: 'javascript:alert(1)',
      },
      [`POST /api/ai/connectors/${connector.id}/disconnect`]: { ...connector, has_secret: false },
    })
    const { user } = await renderApp('/admin/ai/connectors')
    const card = await screen.findByRole('article', { name: 'GitHub' })
    expect(within(card).getByText('Verbunden')).toBeInTheDocument()

    await user.click(within(card).getByRole('button', { name: 'Neu verbinden' }))
    expect(await within(card).findByText(/keine https-Adresse/)).toBeInTheDocument()
    expect(sendBrowserTo).not.toHaveBeenCalled()

    await user.click(within(card).getByRole('button', { name: 'Trennen' }))
    await waitFor(() =>
      expect(api.find('POST', `/api/ai/connectors/${connector.id}/disconnect`)).toHaveLength(1),
    )
    expect(api.find('POST', `/api/ai/connectors/${connector.id}/disconnect`)[0]!.body).toEqual({
      version: 4,
    })
  })

  test('a connector a server uses cannot be deleted, in words', async () => {
    const connector = makeConnector({ id: '00000000-0000-7000-8000-00000000cd03', version: 2 })
    mockApi({
      ...shell,
      'GET /api/ai/connectors': page([connector]),
      'GET /api/ai/oauth-clients': page([]),
      [`DELETE /api/ai/connectors/${connector.id}`]: apiError(409, 'connector.in_use'),
    })
    const { user } = await renderApp('/admin/ai/connectors')
    await user.click(await screen.findByRole('button', { name: 'GitHub-Token löschen' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Löschen' }))
    expect(await within(dialog).findByText(/Ein Server nutzt diesen Konnektor/)).toBeVisible()
  })
})

describe('OAuth apps', () => {
  test('a server’s metadata fills the empty fields; the secret stays write-only', async () => {
    const api = mockApi({
      ...shell,
      'GET /api/ai/connectors': page([]),
      'GET /api/ai/oauth-clients': page([]),
      'POST /api/ai/oauth-clients/discover': {
        status: 'ok',
        resource: 'https://gitlab.com/api/v4/mcp',
        issuer: 'https://gitlab.com',
        authorization_endpoint: 'https://gitlab.com/oauth/authorize',
        token_endpoint: 'https://gitlab.com/oauth/token',
        revocation_endpoint: 'https://gitlab.com/oauth/revoke',
        scopes: 'mcp',
        pkce: true,
        registration: false,
      },
      'POST /api/ai/oauth-clients': { status: 201, body: makeClient() },
    })
    const { user } = await renderApp('/admin/ai/connectors')
    await user.click(await screen.findByRole('button', { name: 'OAuth-App anlegen' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(
      within(dialog).getByLabelText('Adresse des MCP-Servers'),
      'https://gitlab.com/api/v4/mcp',
    )
    await user.click(within(dialog).getByRole('button', { name: 'Ermitteln' }))
    expect(await within(dialog).findByText(/Angaben gefunden und eingetragen/)).toBeVisible()
    expect(within(dialog).getByLabelText('Token-Adresse (token endpoint)')).toHaveValue(
      'https://gitlab.com/oauth/token',
    )
    await user.type(within(dialog).getByLabelText('Name'), 'GitLab-App')
    await user.type(within(dialog).getByLabelText('Client-ID'), 'app-123')
    await user.click(within(dialog).getByLabelText('Neues Geheimnis'))
    await user.type(within(dialog).getByLabelText('Client-Geheimnis'), 's3cret')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(api.find('POST', '/api/ai/oauth-clients')).toHaveLength(1))
    expect(api.find('POST', '/api/ai/oauth-clients')[0]!.body).toEqual({
      name: 'GitLab-App',
      authorization_endpoint: 'https://gitlab.com/oauth/authorize',
      token_endpoint: 'https://gitlab.com/oauth/token',
      revocation_endpoint: 'https://gitlab.com/oauth/revoke',
      client_id: 'app-123',
      token_auth: 'client_secret_post',
      scopes: 'mcp',
      resource: 'https://gitlab.com/api/v4/mcp',
      client_secret: { value: 's3cret' },
    })
  })
})
