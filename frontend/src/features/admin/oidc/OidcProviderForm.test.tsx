import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Permission, Schemas } from '@/lib/api'
import { apiError, makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

type Provider = Schemas['ProviderOut']

const ADMIN: Permission[] = ['user.manage', 'directory.read']

function makeProvider(overrides: Partial<Provider> = {}): Provider {
  return {
    id: '00000000-0000-7000-8000-0000000001a1',
    key: 'google',
    name: 'Google',
    kind: 'google',
    issuer: 'https://accounts.google.com',
    client_id: 'client-123.apps.googleusercontent.com',
    client_secret: { set: true, kind: 'enc' },
    scopes: 'openid email profile',
    trust_email: false,
    allow_signup: true,
    allowed_domains: ['example.com'],
    enabled: true,
    discovered: true,
    callback_url: 'https://herd.example/api/auth/oidc/google/callback',
    version: 3,
    ...overrides,
  }
}

const shell = (permissions: Permission[]) => ({
  'GET /api/auth/me': makeMe(permissions),
  'GET /api/spaces': page([]),
})

describe('sign-in administration', () => {
  test('without user.manage: no menu entry, not found, no provider request', async () => {
    const api = mockApi(shell(['ai.manage']))
    await renderApp('/admin/sign-in')
    expect(await screen.findByRole('heading', { name: 'Seite nicht gefunden' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Anmeldung' })).not.toBeInTheDocument()
    expect(api.calls.filter((c) => c.path.startsWith('/api/admin/oidc'))).toEqual([])
  })

  test('Google is set up with only client id, secret and domains; the secret never comes back', async () => {
    const stored: Provider[] = []
    const api = mockApi({
      ...shell(ADMIN),
      'GET /api/admin/oidc-providers': () => page(stored),
      'GET /api/auth/providers': page([]),
      'POST /api/admin/oidc-providers': () => {
        const created = makeProvider({ enabled: false })
        stored.push(created)
        return { status: 201, body: created }
      },
    })
    const { user } = await renderApp('/admin/sign-in')
    expect(await screen.findByText(/Noch kein Anbieter eingerichtet/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Anmeldung' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Google hinzufügen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Google einrichten' })
    expect(within(dialog).queryByLabelText('Issuer')).not.toBeInTheDocument()
    expect(within(dialog).queryByLabelText(/Kein Secret/)).not.toBeInTheDocument()
    await user.type(within(dialog).getByLabelText('Client-ID'), 'client-123')
    await user.type(within(dialog).getByLabelText('Secret'), 'g-SECRET-1')
    await user.click(within(dialog).getByLabelText('Selbstregistrierung erlauben'))
    await user.click(within(dialog).getByRole('button', { name: 'Anbieter anlegen' }))
    expect(
      await within(dialog).findByText('Mit Selbstregistrierung ist mindestens eine Domain nötig.'),
    ).toBeInTheDocument()
    expect(api.find('POST', '/api/admin/oidc-providers')).toHaveLength(0)

    await user.type(within(dialog).getByLabelText('Erlaubte Domains'), 'example.com\nfirma.de')
    await user.click(within(dialog).getByRole('button', { name: 'Anbieter anlegen' }))
    await waitFor(() => expect(api.find('POST', '/api/admin/oidc-providers')).toHaveLength(1))
    expect(api.find('POST', '/api/admin/oidc-providers')[0]?.body).toEqual({
      kind: 'google',
      client_id: 'client-123',
      client_secret: { value: 'g-SECRET-1' },
      allow_signup: true,
      allowed_domains: ['example.com', 'firma.de'],
      enabled: false,
    })
    const card = await screen.findByRole('article', { name: 'Google' })
    expect(within(card).getByText(/api\/auth\/oidc\/google\/callback/)).toBeInTheDocument()
    expect(screen.queryByText(/g-SECRET-1/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Google hinzufügen' })).not.toBeInTheDocument()
  })

  test('a generic provider signs people up only when its addresses are trusted', async () => {
    const api = mockApi({
      ...shell(ADMIN),
      'GET /api/admin/oidc-providers': page([]),
      'GET /api/auth/providers': page([]),
      'POST /api/admin/oidc-providers': () => ({
        status: 201,
        body: makeProvider({ kind: 'generic', key: 'firma', name: 'Firma', trust_email: true }),
      }),
    })
    const { user } = await renderApp('/admin/sign-in')
    await user.click(await screen.findByRole('button', { name: 'Anderen Anbieter hinzufügen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Anbieter einrichten' })
    await user.type(within(dialog).getByLabelText('Schlüssel'), 'firma')
    await user.type(within(dialog).getByLabelText('Name'), 'Firma')
    await user.type(within(dialog).getByLabelText('Issuer'), 'https://login.firma.example')
    await user.type(within(dialog).getByLabelText('Client-ID'), 'herd')
    await user.type(within(dialog).getByLabelText('Secret'), 'f-SECRET-1')
    await user.type(within(dialog).getByLabelText('Erlaubte Domains'), 'firma.example')
    const signup = within(dialog).getByLabelText('Selbstregistrierung erlauben')
    await user.click(signup)
    await user.click(within(dialog).getByRole('button', { name: 'Anbieter anlegen' }))
    const refusal =
      'Selbstregistrierung geht nur, wenn du den E-Mail-Adressen dieses Anbieters vertraust.'
    expect(await within(dialog).findByText(refusal)).toBeInTheDocument()
    expect(signup).toHaveAttribute('aria-invalid', 'true')
    expect(api.find('POST', '/api/admin/oidc-providers')).toHaveLength(0)

    await user.click(within(dialog).getByLabelText('E-Mail-Adressen dieses Anbieters vertrauen'))
    await user.click(within(dialog).getByRole('button', { name: 'Anbieter anlegen' }))
    await waitFor(() => expect(api.find('POST', '/api/admin/oidc-providers')).toHaveLength(1))
    expect(api.find('POST', '/api/admin/oidc-providers')[0]?.body).toMatchObject({
      kind: 'generic',
      trust_email: true,
      allow_signup: true,
      allowed_domains: ['firma.example'],
    })
  })

  test('editing keeps the secret field empty and unsent; a stale version offers a reload', async () => {
    const provider = makeProvider()
    const api = mockApi({
      ...shell(ADMIN),
      'GET /api/admin/oidc-providers': page([provider]),
      'GET /api/admin/oidc-providers/:id': { ...provider, version: 4 },
      'PATCH /api/admin/oidc-providers/:id': apiError(409, 'oidc.version_conflict'),
    })
    const { user } = await renderApp('/admin/sign-in')
    const card = await screen.findByRole('article', { name: 'Google' })
    await user.click(within(card).getByRole('button', { name: 'Google bearbeiten' }))
    const dialog = await screen.findByRole('dialog', { name: 'Anbieter bearbeiten' })
    expect(within(dialog).getByLabelText('Gespeichertes Secret behalten')).toBeChecked()
    expect(within(dialog).queryByLabelText('Secret')).not.toBeInTheDocument()
    expect(within(dialog).getByLabelText('Erlaubte Domains')).toHaveValue('example.com')

    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    expect(await within(dialog).findByText(/inzwischen geändert/)).toBeInTheDocument()
    const body = api.find('PATCH', `/api/admin/oidc-providers/${provider.id}`)[0]?.body as object
    expect(body).not.toHaveProperty('client_secret')
    expect(body).not.toHaveProperty('issuer')
    expect(body).toMatchObject({ version: 3, allowed_domains: ['example.com'] })

    await user.click(within(dialog).getByRole('button', { name: 'Aktuelle Fassung laden' }))
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() =>
      expect(api.find('PATCH', `/api/admin/oidc-providers/${provider.id}`)).toHaveLength(2),
    )
    expect(api.find('PATCH', `/api/admin/oidc-providers/${provider.id}`)[1]?.body).toMatchObject({
      version: 4,
    })
  })

  test('the check words the result by its code, never the provider text', async () => {
    const provider = makeProvider({ kind: 'generic', key: 'firma', name: 'Firmen-Login' })
    mockApi({
      ...shell(ADMIN),
      'GET /api/admin/oidc-providers': page([provider]),
      'POST /api/admin/oidc-providers/:id/check': { ok: false, code: 'oidc.issuer_mismatch' },
    })
    const { user } = await renderApp('/admin/sign-in')
    const card = await screen.findByRole('article', { name: 'Firmen-Login' })
    await user.click(within(card).getByRole('button', { name: 'Prüfen' }))
    expect(await within(card).findByRole('status')).toHaveTextContent(
      'Prüfung fehlgeschlagen. Das Discovery-Dokument nennt einen anderen Issuer.',
    )
  })

  test('without HERD_PUBLIC_URL there is no callback address, and it says why', async () => {
    mockApi({
      ...shell(ADMIN),
      'GET /api/admin/oidc-providers': page([makeProvider({ callback_url: null, enabled: false })]),
    })
    await renderApp('/admin/sign-in')
    const card = await screen.findByRole('article', { name: 'Google' })
    expect(within(card).getByText(/Ohne HERD_PUBLIC_URL/)).toBeInTheDocument()
  })
})
