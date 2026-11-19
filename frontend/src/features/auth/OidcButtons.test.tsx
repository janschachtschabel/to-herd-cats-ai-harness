import { screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { apiError, makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

const signedOut = { 'GET /api/auth/me': apiError(401, 'auth.required') }

describe('sign-in with a provider', () => {
  test('no provider switched on: only the password form, no divider', async () => {
    mockApi({ ...signedOut, 'GET /api/auth/providers': page([]) })
    await renderApp('/login')
    expect(await screen.findByLabelText('E-Mail-Adresse')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Anmelden mit|Mit Google/ })).not.toBeInTheDocument()
    expect(screen.queryByText('oder mit E-Mail und Passwort')).not.toBeInTheDocument()
  })

  test('Google and another provider: one link each to its start, above the form', async () => {
    mockApi({
      ...signedOut,
      'GET /api/auth/providers': page([
        { key: 'google', name: 'Google', kind: 'google' },
        { key: 'firma', name: 'Firmen-Login', kind: 'generic' },
      ]),
    })
    await renderApp('/login')
    const google = await screen.findByRole('link', { name: 'Mit Google anmelden' })
    expect(google).toHaveAttribute('href', '/api/auth/oidc/google/start')
    expect(screen.getByRole('link', { name: 'Anmelden mit Firmen-Login' })).toHaveAttribute(
      'href',
      '/api/auth/oidc/firma/start',
    )
    expect(screen.getByText('oder mit E-Mail und Passwort')).toBeInTheDocument()
  })

  test('a refused sign-in comes back with its code and shows its text', async () => {
    mockApi({
      ...signedOut,
      'GET /api/auth/providers': page([{ key: 'google', name: 'Google', kind: 'google' }]),
    })
    await renderApp('/login?error=oidc.domain_not_allowed')
    expect(
      await screen.findByText('Konten dieser Domain können sich hier nicht selbst registrieren.'),
    ).toBeInTheDocument()
  })

  test('an unknown code falls back to a general text', async () => {
    mockApi({ ...signedOut, 'GET /api/auth/providers': page([]) })
    await renderApp('/login?error=oidc.something_new')
    expect(await screen.findByText('Die Anmeldung hat nicht geklappt.')).toBeInTheDocument()
  })

  test('a code that is not one of ours is dropped, never shown', async () => {
    mockApi({ ...signedOut, 'GET /api/auth/providers': page([]) })
    await renderApp('/login?error=%3Cb%3Ehallo%3C%2Fb%3E')
    expect(await screen.findByLabelText('E-Mail-Adresse')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByText('Die Anmeldung hat nicht geklappt.')).not.toBeInTheDocument()
  })

  test('the profile lists linked accounts and offers the providers not yet linked', async () => {
    mockApi({
      'GET /api/auth/me': makeMe([]),
      'GET /api/spaces': page([]),
      'GET /api/auth/providers': page([
        { key: 'google', name: 'Google', kind: 'google' },
        { key: 'firma', name: 'Firmen-Login', kind: 'generic' },
      ]),
      'GET /api/auth/me/identities': page([
        {
          id: '00000000-0000-7000-8000-0000000001d1',
          provider_key: 'google',
          provider_name: 'Google',
          provider_kind: 'google',
          created_at: '2026-11-15T08:00:00Z',
          last_login_at: null,
        },
      ]),
    })
    await renderApp('/profile?link_error=oidc.identity_taken')
    expect(await screen.findByRole('heading', { name: 'Verknüpfte Konten' })).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: 'Verknüpfung mit Google lösen' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mit Firmen-Login verknüpfen' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mit Google verknüpfen' })).not.toBeInTheDocument()
    expect(
      screen.getByText('Dieses Konto ist schon mit einer anderen Person verknüpft.'),
    ).toBeInTheDocument()
  })
})
