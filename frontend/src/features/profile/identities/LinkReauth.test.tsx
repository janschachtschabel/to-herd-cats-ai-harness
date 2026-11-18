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
    expect(within(dialog).getByText(/über deinen Anbieter/)).toBeInTheDocument()
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
