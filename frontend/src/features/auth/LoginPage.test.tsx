import { screen, waitFor } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { apiError, makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

describe('login', () => {
  test('login posts credentials and redirects to /spaces', async () => {
    const me = makeMe(['space.create'])
    let loggedIn = false
    const api = mockApi({
      'GET /api/auth/me': () => (loggedIn ? me : apiError(401, 'auth.required')),
      'POST /api/auth/login': () => {
        loggedIn = true
        return me
      },
      'GET /api/spaces': page([]),
    })
    const { router, user } = await renderApp('/login')

    await user.type(screen.getByLabelText('E-Mail-Adresse'), 'mia@example.com')
    await user.type(screen.getByLabelText('Passwort'), 'geheim-genug')
    await user.click(screen.getByRole('button', { name: 'Anmelden' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/spaces'))
    const [login] = api.find('POST', '/api/auth/login')
    expect(login?.body).toEqual({ email: 'mia@example.com', password: 'geheim-genug' })
    expect(login?.headers.get('X-Requested-With')).toBe('herd')
    expect(await screen.findByRole('heading', { name: 'Bereiche', level: 1 })).toBeInTheDocument()
  })

  test('wrong credentials show the translated message and the trace id', async () => {
    mockApi({
      'GET /api/auth/me': apiError(401, 'auth.required'),
      'POST /api/auth/login': apiError(401, 'auth.invalid_credentials'),
    })
    const { user } = await renderApp('/login')
    await user.type(screen.getByLabelText('E-Mail-Adresse'), 'mia@example.com')
    await user.type(screen.getByLabelText('Passwort'), 'falsch')
    await user.click(screen.getByRole('button', { name: 'Anmelden' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('E-Mail-Adresse oder Passwort ist falsch.')
    expect(alert).toHaveTextContent('4bf92f3577b34da6a3ce929d0e0e4736')
  })

  test('a visit without a session goes to the login and comes back after it', async () => {
    mockApi({ 'GET /api/auth/me': apiError(401, 'auth.required') })
    const { router } = await renderApp('/admin/users')
    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.search).toEqual({ redirect: '/admin/users' })
  })

  test('a 401 on any request sends the person to the login', async () => {
    mockApi({
      'GET /api/auth/me': makeMe(['space.create']),
      'GET /api/spaces': apiError(401, 'auth.session_invalid'),
    })
    const { router } = await renderApp('/spaces')
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
  })
})
