import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { User } from '@/lib/api'
import { ADMIN_PERMISSIONS, apiError, makeMe, makeUser, mockApi, page } from '@/test/api'
import { makeActivity, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'

const WAITING_SINCE = '2026-11-15T08:00:00Z'

function waiting(overrides: Partial<User> = {}): User {
  return makeUser({
    id: 'nina',
    name: 'Nina Neu',
    email: 'nina@neu.example',
    is_active: false,
    awaiting_approval_since: WAITING_SINCE,
    version: 3,
    ...overrides,
  })
}

describe('self-registered accounts awaiting approval (plan M9 task 5b)', () => {
  test('the navigation counts them; the filter lists them; Freigeben approves', async () => {
    let nina = waiting()
    const lea = makeUser({ name: 'Lea Löwe' })
    const api = mockApi({
      'GET /api/auth/me': makeMe(ADMIN_PERMISSIONS),
      'GET /api/spaces': page([]),
      'GET /api/admin/users/pending/count': () => ({ count: nina.awaiting_approval_since ? 1 : 0 }),
      'GET /api/admin/users': (call) =>
        page(
          call.query.get('pending') === 'true'
            ? nina.awaiting_approval_since
              ? [nina]
              : []
            : [lea, nina],
        ),
      'POST /api/admin/users/nina/approve': () => {
        nina = { ...nina, is_active: true, awaiting_approval_since: null, version: 4 }
        return nina
      },
    })
    const { user, router } = await renderApp('/admin/users')
    const nav = await screen.findByRole('link', { name: /Personen/ })
    expect(await within(nav).findByText('1 Konto wartet auf Freigabe')).toBeInTheDocument()
    expect(
      await screen.findByText('Wartet auf Freigabe', { selector: '[data-slot="badge"]' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: /Wartet auf Freigabe/ }))
    await waitFor(() => expect(router.state.location.search).toEqual({ filter: 'pending' }))
    expect(
      await screen.findByText(/haben sich selbst über einen Anmeldeanbieter registriert/),
    ).toBeInTheDocument()
    expect(screen.queryByRole('cell', { name: /Lea Löwe/ })).not.toBeInTheDocument()
    expect(screen.getByRole('cell', { name: /Nina Neu/ })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Nina Neu freigeben' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('Nina Neu kann sich danach als Mitglied anmelden')
    await user.click(within(dialog).getByRole('button', { name: 'Freigeben' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(api.find('POST', '/api/admin/users/nina/approve')[0]?.body).toEqual({ version: 3 })
    expect(await screen.findByText('Niemand wartet auf Freigabe.')).toBeInTheDocument()
    await waitFor(() =>
      expect(within(nav).queryByText(/wartet auf Freigabe/)).not.toBeInTheDocument(),
    )
  })

  test('Ablehnen rejects; a decision made meanwhile shows the conflict', async () => {
    const api = mockApi({
      'GET /api/auth/me': makeMe(ADMIN_PERMISSIONS),
      'GET /api/spaces': page([]),
      'GET /api/admin/users/pending/count': { count: 1 },
      'GET /api/admin/users': page([waiting()]),
      'POST /api/admin/users/nina/reject': apiError(409, 'users.not_pending'),
    })
    const { user } = await renderApp('/admin/users?filter=pending')
    await user.click(await screen.findByRole('button', { name: 'Nina Neu ablehnen' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('wird gelöscht')
    expect(dialog).toHaveTextContent('Die Adresse ist danach wieder frei')
    await user.click(within(dialog).getByRole('button', { name: 'Ablehnen' }))
    expect(
      await within(dialog).findByText('Über dieses Konto wurde inzwischen schon entschieden.'),
    ).toBeInTheDocument()
    expect(api.find('POST', '/api/admin/users/nina/reject')[0]?.body).toEqual({ version: 3 })
  })

  test('a waiting account offers no reactivation and no sign-out', async () => {
    mockApi({
      'GET /api/auth/me': makeMe(ADMIN_PERMISSIONS),
      'GET /api/spaces': page([]),
      'GET /api/admin/users/pending/count': { count: 1 },
      'GET /api/admin/users': page([waiting()]),
    })
    await renderApp('/admin/users')
    expect(await screen.findByRole('button', { name: 'Nina Neu freigeben' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Nina Neu reaktivieren' })).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Nina Neu überall abmelden/ }),
    ).not.toBeInTheDocument()
  })

  test('without user.manage nobody asks for the count', async () => {
    const api = mockApi({
      'GET /api/auth/me': makeMe(['audit.read', 'space.create']),
      'GET /api/spaces': page([]),
      'GET /api/admin/audit': page([]),
    })
    await renderApp('/admin/audit')
    expect(await screen.findByText('Keine Einträge.')).toBeInTheDocument()
    expect(api.find('GET', '/api/admin/users/pending/count')).toEqual([])
  })

  test('the sign-in page says the account waits for approval', async () => {
    mockApi({
      'GET /api/auth/me': apiError(401, 'auth.required'),
      'GET /api/auth/providers': page([]),
    })
    const { user, router } = await renderApp('/login?error=oidc.account_pending')
    expect(
      await screen.findByRole('heading', { name: 'Dein Konto wartet auf Freigabe' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/wartet auf Freigabe durch eine Administratorin oder einen Administrator/),
    ).toBeInTheDocument()
    expect(screen.queryByLabelText('Passwort')).not.toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Zur Anmeldung' }))
    await waitFor(() => expect(router.state.location.search).toEqual({}))
    expect(await screen.findByLabelText('Passwort')).toBeInTheDocument()
  })

  test('the activity tells admins and opens the waiting accounts', async () => {
    const author = { type: 'user' as const, id: 'nina', name: 'Nina Neu' }
    const entry = (awaiting: boolean) =>
      makeActivity({
        reason: 'signup',
        conversation: null,
        message_id: null,
        author,
        snippet: '',
        account: { id: 'nina', awaiting },
      })
    mockApi({
      ...shellRoutes(makeMe(ADMIN_PERMISSIONS)),
      'POST /api/activity/:id/read': { status: 204 },
      'GET /api/admin/users/pending/count': { count: 1 },
      'GET /api/admin/users': page([waiting()]),
      'GET /api/activity': page([entry(true), entry(false)]),
    })
    const { user, router } = await renderApp('/activity')
    expect(
      await screen.findByText('Nina Neu hat sich registriert und wartet auf Freigabe.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Nina Neu hat sich registriert; über die Freigabe ist entschieden.'),
    ).toBeInTheDocument()
    const [first] = screen.getAllByRole('button', { name: 'Öffnen' })
    await user.click(first!)
    await waitFor(() => expect(router.state.location.pathname).toBe('/admin/users'))
    expect(router.state.location.search).toEqual({ filter: 'pending' })
  })
})
