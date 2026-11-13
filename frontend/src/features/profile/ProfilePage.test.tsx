import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Me } from '@/lib/api'
import { apiError, type Call, makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

/** The API side of the person's own settings: PATCH answers with the new `me`. */
function profileApi(me: Me) {
  let current = me
  return mockApi({
    'GET /api/auth/me': () => current,
    'GET /api/spaces': page([]),
    'PATCH /api/auth/me': (call: Call) => {
      const body = call.body as { locale: 'de' | 'en'; version: number }
      current = { ...current, user: { ...current.user, ...body, version: body.version + 1 } }
      return current
    },
  })
}

describe('profile', () => {
  test('the interface speaks the language stored for the person', async () => {
    mockApi({
      'GET /api/auth/me': makeMe(['space.create'], { locale: 'en' }),
      'GET /api/spaces': page([]),
    })
    await renderApp('/spaces')
    expect(await screen.findByRole('heading', { name: 'Spaces', level: 1 })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
  })

  test('the person changes their language on the profile page', async () => {
    const api = profileApi(makeMe(['space.create']))
    const { user } = await renderApp('/profile')
    expect(await screen.findByRole('heading', { name: 'Profil', level: 1 })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Sprache'), 'en')
    expect(await screen.findByRole('heading', { name: 'Profile', level: 1 })).toBeInTheDocument()
    await waitFor(() =>
      expect(api.find('PATCH', '/api/auth/me')[0]?.body).toEqual({ locale: 'en', version: 1 }),
    )
  })

  test('the user menu leads to the profile and stores the language there too', async () => {
    const api = profileApi(makeMe(['space.create']))
    const { user, router } = await renderApp('/spaces')
    await user.click(screen.getByRole('button', { name: 'Menü von Mia Muster' }))
    await user.click(screen.getByRole('menuitemradio', { name: 'English' }))
    expect(await screen.findByRole('heading', { name: 'Spaces', level: 1 })).toBeInTheDocument()
    await waitFor(() =>
      expect(api.find('PATCH', '/api/auth/me')[0]?.body).toEqual({ locale: 'en', version: 1 }),
    )
    await user.click(screen.getByRole('button', { name: 'Menu of Mia Muster' }))
    await user.click(screen.getByRole('menuitem', { name: 'Profile and settings' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/profile'))
  })

  test('the person changes their password with the current one', async () => {
    const api = mockApi({
      'GET /api/auth/me': makeMe(['space.create']),
      'GET /api/spaces': page([]),
      'POST /api/auth/me/password': (call: Call) =>
        (call.body as { current_password: string }).current_password === 'altes-passwort-1'
          ? { status: 204 }
          : apiError(422, 'auth.wrong_password'),
    })
    const { user } = await renderApp('/profile')
    const form = await screen.findByRole('form', { name: 'Passwort ändern' })
    await user.type(within(form).getByLabelText('Aktuelles Passwort'), 'falsch')
    await user.type(within(form).getByLabelText('Neues Passwort'), 'neues-passwort-1')
    await user.click(within(form).getByRole('button', { name: 'Passwort ändern' }))
    expect(await within(form).findByText('Das aktuelle Passwort stimmt nicht.')).toBeInTheDocument()

    await user.clear(within(form).getByLabelText('Aktuelles Passwort'))
    await user.type(within(form).getByLabelText('Aktuelles Passwort'), 'altes-passwort-1')
    await user.click(within(form).getByRole('button', { name: 'Passwort ändern' }))
    expect(await within(form).findByRole('status')).toHaveTextContent(
      'Passwort geändert. Andere Sitzungen sind abgemeldet.',
    )
    expect(api.find('POST', '/api/auth/me/password').at(-1)?.body).toEqual({
      current_password: 'altes-passwort-1',
      new_password: 'neues-passwort-1',
    })
    expect(within(form).getByLabelText('Neues Passwort')).toHaveValue('')
  })

  test('a too short new password is refused before sending', async () => {
    const api = mockApi({ 'GET /api/auth/me': makeMe([]), 'GET /api/spaces': page([]) })
    const { user } = await renderApp('/profile')
    const form = await screen.findByRole('form', { name: 'Passwort ändern' })
    await user.type(within(form).getByLabelText('Aktuelles Passwort'), 'altes-passwort-1')
    await user.type(within(form).getByLabelText('Neues Passwort'), 'kurz')
    await user.click(within(form).getByRole('button', { name: 'Passwort ändern' }))
    expect(await within(form).findByText('Mindestens 10 Zeichen.')).toBeInTheDocument()
    expect(api.find('POST', '/api/auth/me/password')).toEqual([])
  })
})
