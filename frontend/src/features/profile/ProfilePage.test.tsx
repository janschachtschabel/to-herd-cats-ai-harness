import { screen, waitFor } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Me } from '@/lib/api'
import { type Call, makeMe, mockApi, page } from '@/test/api'
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
})
