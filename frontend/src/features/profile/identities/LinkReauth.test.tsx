import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { apiError, type Call, makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

const PROVIDER_URL = 'https://idp.example/authorize?state=x'

function linkApi() {
  return mockApi({
    'GET /api/auth/me': makeMe([]),
    'GET /api/spaces': page([]),
    'GET /api/auth/me/totp': { enabled_at: null, recovery_codes_left: 0, unavailable: null },
    'GET /api/auth/me/sessions': page([]),
    'GET /api/auth/providers': page([{ key: 'firma', name: 'Firmen-Login', kind: 'generic' }]),
    'GET /api/auth/me/identities': page([]),
    'POST /api/auth/me/identities/:key/link': (call: Call) => {
      const password = (call.body as { password?: string } | undefined)?.password
      if (!password) return apiError(403, 'auth.reauth_required')
      if (password !== 'richtiges-passwort') return apiError(422, 'auth.wrong_password')
      return { url: PROVIDER_URL }
    },
  })
}

describe('linking an account asks to sign in again', () => {
  afterEach(() => vi.unstubAllGlobals())

  test('the password goes with the link; a wrong one stays in the dialog', async () => {
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
    const api = linkApi()
    const { user } = await renderApp('/profile')
    await user.click(await screen.findByRole('button', { name: 'Mit Firmen-Login verknüpfen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Erneut anmelden' })
    expect(within(dialog).getByText(/über einen Anbieter/)).toBeInTheDocument()
    expect(screen.queryByText('Bitte melde dich erneut an.')).not.toBeInTheDocument()

    await user.type(within(dialog).getByLabelText('Aktuelles Passwort'), 'falsch-falsch')
    await user.click(within(dialog).getByRole('button', { name: 'Weiter zum Anbieter' }))
    expect(
      await within(dialog).findByText('Das aktuelle Passwort stimmt nicht.'),
    ).toBeInTheDocument()

    await user.clear(within(dialog).getByLabelText('Aktuelles Passwort'))
    await user.type(within(dialog).getByLabelText('Aktuelles Passwort'), 'richtiges-passwort')
    await user.click(within(dialog).getByRole('button', { name: 'Weiter zum Anbieter' }))
    await waitFor(() => expect(assign).toHaveBeenCalledWith(PROVIDER_URL))
    const calls = api.find('POST', '/api/auth/me/identities/firma/link')
    expect(calls.map((c) => c.body)).toEqual([
      undefined,
      { password: 'falsch-falsch' },
      { password: 'richtiges-passwort' },
    ])
  })
})

describe('without a password the proof is a fresh sign-in at a linked provider', () => {
  test('the dialog offers it, and a stale one comes back with its reason', async () => {
    mockApi({
      'GET /api/auth/me': makeMe([]),
      'GET /api/spaces': page([]),
      'GET /api/auth/me/totp': { enabled_at: null, recovery_codes_left: 0, unavailable: null },
      'GET /api/auth/me/sessions': page([]),
      'GET /api/auth/providers': page([
        { key: 'firma', name: 'Firmen-Login', kind: 'generic' },
        { key: 'google', name: 'Google', kind: 'google' },
      ]),
      'GET /api/auth/me/identities': page([
        {
          id: '00000000-0000-0000-0000-0000000000a1',
          provider_key: 'firma',
          provider_name: 'Firmen-Login',
          provider_kind: 'generic',
          created_at: '2026-11-01T09:00:00Z',
          last_login_at: null,
        },
      ]),
      'POST /api/auth/me/identities/:key/link': () => apiError(403, 'auth.reauth_required'),
    })
    const { user } = await renderApp('/profile?link_error=oidc.reauth_stale')
    expect(await screen.findByText(/älter als 10 Minuten/)).toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: 'Mit Google verknüpfen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Erneut anmelden' })
    const proof = within(dialog).getByRole('link', { name: 'Erneut über Firmen-Login anmelden' })
    expect(proof).toHaveAttribute('href', '/api/auth/oidc/firma/start?reauth=true')
    expect(within(dialog).queryByRole('link', { name: /Google/ })).not.toBeInTheDocument()
  })
})
