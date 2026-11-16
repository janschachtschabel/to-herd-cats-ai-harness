import { screen, waitFor } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { apiError, makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

const WAITING = { status: 202, body: { second_factor: 'totp', expires_at: '2026-11-16T12:05:00Z' } }

async function passwordStep(user: Awaited<ReturnType<typeof renderApp>>['user']) {
  await user.type(screen.getByLabelText('E-Mail-Adresse'), 'mia@example.com')
  await user.type(screen.getByLabelText('Passwort'), 'geheim-genug')
  await user.click(screen.getByRole('button', { name: 'Anmelden' }))
}

describe('sign-in with a second factor', () => {
  test('the password step asks for the code, which signs in', async () => {
    const me = makeMe(['space.create'])
    let signedIn = false
    const api = mockApi({
      'GET /api/auth/me': () => (signedIn ? me : apiError(401, 'auth.required')),
      'POST /api/auth/login': WAITING,
      'POST /api/auth/login/second-factor': () => {
        signedIn = true
        return me
      },
      'GET /api/spaces': page([]),
    })
    const { router, user } = await renderApp('/login')
    await passwordStep(user)

    const code = await screen.findByLabelText('Code aus der Authenticator-App')
    expect(screen.getByRole('heading', { name: 'Zweiter Faktor', level: 1 })).toBeInTheDocument()
    expect(code).toHaveAttribute('autocomplete', 'one-time-code')
    await user.type(code, '123456')
    await user.click(screen.getByRole('button', { name: 'Bestätigen' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/spaces'))
    const [sent] = api.find('POST', '/api/auth/login/second-factor')
    expect(sent?.body).toEqual({ code: '123456' })
  })

  test('a recovery code instead of the code', async () => {
    const me = makeMe([])
    let signedIn = false
    const api = mockApi({
      'GET /api/auth/me': () => (signedIn ? me : apiError(401, 'auth.required')),
      'POST /api/auth/login': WAITING,
      'POST /api/auth/login/second-factor': () => {
        signedIn = true
        return me
      },
      'GET /api/spaces': page([]),
    })
    const { user } = await renderApp('/login')
    await passwordStep(user)
    await user.click(
      await screen.findByRole('button', { name: 'Wiederherstellungscode verwenden' }),
    )
    await user.type(screen.getByLabelText('Wiederherstellungscode'), 'ABCDEF-GHIJKL-MNOPQR-STUVWX')
    await user.click(screen.getByRole('button', { name: 'Bestätigen' }))
    await waitFor(() => expect(api.find('POST', '/api/auth/login/second-factor')).toHaveLength(1))
    expect(api.find('POST', '/api/auth/login/second-factor')[0]?.body).toEqual({
      recovery_code: 'ABCDEF-GHIJKL-MNOPQR-STUVWX',
    })
  })

  test('a wrong code says so and the person stays on the step', async () => {
    mockApi({
      'GET /api/auth/me': apiError(401, 'auth.required'),
      'POST /api/auth/login': WAITING,
      'POST /api/auth/login/second-factor': apiError(401, 'auth.second_factor_invalid'),
    })
    const { router, user } = await renderApp('/login')
    await passwordStep(user)
    await user.type(await screen.findByLabelText('Code aus der Authenticator-App'), '000000')
    await user.click(screen.getByRole('button', { name: 'Bestätigen' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Der Code stimmt nicht')
    expect(router.state.location.pathname).toBe('/login')
  })

  test('an expired sign-in goes back to the password', async () => {
    mockApi({
      'GET /api/auth/me': apiError(401, 'auth.required'),
      'POST /api/auth/login': WAITING,
      'POST /api/auth/login/second-factor': apiError(401, 'auth.second_factor_expired'),
    })
    const { user } = await renderApp('/login')
    await passwordStep(user)
    await user.type(await screen.findByLabelText('Code aus der Authenticator-App'), '123456')
    await user.click(screen.getByRole('button', { name: 'Bestätigen' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('abgelaufen')
    await user.click(screen.getByRole('button', { name: 'Zurück zur Anmeldung' }))
    expect(await screen.findByLabelText('Passwort')).toBeInTheDocument()
  })

  test('after a provider the page opens on the second step', async () => {
    mockApi({ 'GET /api/auth/me': apiError(401, 'auth.required') })
    await renderApp('/login?second_factor=totp')
    expect(await screen.findByLabelText('Code aus der Authenticator-App')).toBeInTheDocument()
    expect(screen.queryByLabelText('Passwort')).not.toBeInTheDocument()
  })
})
