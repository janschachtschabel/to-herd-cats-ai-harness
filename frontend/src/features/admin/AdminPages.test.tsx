import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { User } from '@/lib/api'
import { ADMIN_PERMISSIONS, apiError, type Call, makeMe, makeUser, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

describe('administration', () => {
  test.each([
    '/admin',
    '/admin/users',
    '/admin/groups',
    '/admin/groups/x',
    '/admin/audit',
    '/admin/tags',
  ])('member sees no admin routes; direct navigation shows not-found (%s)', async (path) => {
    const api = mockApi({
      'GET /api/auth/me': makeMe(['space.create']),
      'GET /api/spaces': page([]),
    })
    await renderApp(path)
    expect(await screen.findByRole('heading', { name: 'Seite nicht gefunden' })).toBeInTheDocument()
    expect(screen.queryByText('Verwaltung')).not.toBeInTheDocument()
    expect(api.calls.filter((c) => c.path.startsWith('/api/admin'))).toEqual([])
  })

  test('/admin opens the first administration page one may use', async () => {
    mockApi({
      'GET /api/auth/me': makeMe(['audit.read']),
      'GET /api/spaces': page([]),
      'GET /api/admin/audit': page([]),
    })
    const { router } = await renderApp('/admin')
    await waitFor(() => expect(router.state.location.pathname).toBe('/admin/audit'))
    expect(await screen.findByText('Keine Einträge.')).toBeInTheDocument()
  })

  test('admin adds a person', async () => {
    const people: User[] = [makeUser({ name: 'Lea Löwe', last_login_at: '2026-11-12T09:30:00Z' })]
    const api = mockApi({
      'GET /api/auth/me': makeMe(ADMIN_PERMISSIONS),
      'GET /api/spaces': page([]),
      'GET /api/admin/users': () => page(people),
      'POST /api/admin/users': (call) => {
        const created = makeUser({ ...(call.body as Partial<User>) })
        people.push(created)
        return { status: 201, body: created }
      },
    })
    const { user } = await renderApp('/admin/users')
    expect(await screen.findByRole('cell', { name: /Lea Löwe/ })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Person anlegen' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Name'), 'Jan Jansen')
    await user.type(within(dialog).getByLabelText('E-Mail-Adresse'), 'jan@example.com')
    await user.type(within(dialog).getByLabelText('Passwort'), 'kurz')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    expect(await within(dialog).findByText('Mindestens 10 Zeichen.')).toBeInTheDocument()
    expect(api.find('POST', '/api/admin/users')).toEqual([])

    await user.type(within(dialog).getByLabelText('Passwort'), '-lang-genug')
    await user.selectOptions(within(dialog).getByLabelText('Rolle'), 'Gast')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(api.find('POST', '/api/admin/users')[0]?.body).toEqual({
      name: 'Jan Jansen',
      email: 'jan@example.com',
      password: 'kurz-lang-genug',
      system_role: 'guest',
      locale: 'de',
    })
    expect(await screen.findByRole('cell', { name: /Jan Jansen/ })).toBeInTheDocument()
  })

  test('a taken email shows the backend message and keeps the form', async () => {
    mockApi({
      'GET /api/auth/me': makeMe(ADMIN_PERMISSIONS),
      'GET /api/spaces': page([]),
      'GET /api/admin/users': page([]),
      'POST /api/admin/users': apiError(409, 'users.email_taken'),
    })
    const { user } = await renderApp('/admin/users')
    expect(await screen.findByText('Noch keine Personen.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Person anlegen' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Name'), 'Jan')
    await user.type(within(dialog).getByLabelText('E-Mail-Adresse'), 'jan@example.com')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    expect(
      await within(dialog).findByText('Diese E-Mail-Adresse ist schon vergeben.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByLabelText('Name')).toHaveValue('Jan')
  })

  test('admin changes a role and deactivates a person after confirming', async () => {
    const lea = makeUser({ name: 'Lea Löwe', version: 2 })
    const api = mockApi({
      'GET /api/auth/me': makeMe(ADMIN_PERMISSIONS),
      'GET /api/spaces': page([]),
      'GET /api/admin/users': page([lea]),
      'PATCH /api/admin/users/:id': { ...lea, system_role: 'admin', version: 3 },
      'POST /api/admin/users/:id/deactivate': { status: 204 },
    })
    const { user } = await renderApp('/admin/users')
    await user.click(await screen.findByRole('button', { name: 'Lea Löwe bearbeiten' }))
    const dialog = await screen.findByRole('dialog')
    await user.selectOptions(within(dialog).getByLabelText('Rolle'), 'Administrator')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() =>
      expect(api.find('PATCH', `/api/admin/users/${lea.id}`)[0]?.body).toEqual({
        name: 'Lea Löwe',
        system_role: 'admin',
        locale: 'de',
        password: null,
        version: 2,
      }),
    )

    await user.click(screen.getByRole('button', { name: 'Lea Löwe deaktivieren' }))
    const confirm = await screen.findByRole('dialog', { name: 'Person deaktivieren?' })
    await user.click(within(confirm).getByRole('button', { name: 'Deaktivieren' }))
    await waitFor(() =>
      expect(api.find('POST', `/api/admin/users/${lea.id}/deactivate`)).toHaveLength(1),
    )
  })

  test('an admin signs a person out everywhere', async () => {
    const lea = makeUser({ name: 'Lea Löwe', version: 2 })
    const api = mockApi({
      'GET /api/auth/me': makeMe(ADMIN_PERMISSIONS),
      'GET /api/spaces': page([]),
      'GET /api/admin/users': page([lea]),
      'POST /api/admin/users/:id/sign-out': { status: 204 },
    })
    const { user } = await renderApp('/admin/users')
    await user.click(await screen.findByRole('button', { name: 'Lea Löwe überall abmelden' }))
    const confirm = await screen.findByRole('dialog', { name: 'Überall abmelden?' })
    await user.click(within(confirm).getByRole('button', { name: 'Abmelden' }))
    await waitFor(() =>
      expect(api.find('POST', `/api/admin/users/${lea.id}/sign-out`)).toHaveLength(1),
    )
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  test('an admin editing their own account sees the change as themselves', async () => {
    let me = makeMe(ADMIN_PERMISSIONS)
    mockApi({
      'GET /api/auth/me': () => me,
      'GET /api/spaces': page([]),
      'GET /api/admin/users': () => page([me.user]),
      'PATCH /api/admin/users/:id': (call: Call) => {
        me = { ...me, user: { ...me.user, ...(call.body as Partial<User>), version: 2 } }
        return me.user
      },
    })
    const { user } = await renderApp('/admin/users')
    await user.click(await screen.findByRole('button', { name: 'Mia Muster bearbeiten' }))
    const dialog = await screen.findByRole('dialog')
    await user.clear(within(dialog).getByLabelText('Name'))
    await user.type(within(dialog).getByLabelText('Name'), 'Mia Neu')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    expect(await screen.findByRole('button', { name: 'Menü von Mia Neu' })).toBeInTheDocument()
  })

  test('admin adds a person to a group', async () => {
    const lea = makeUser({ name: 'Lea Löwe' })
    const members: { member_type: 'user'; member_id: string; name: string }[] = []
    const api = mockApi({
      'GET /api/auth/me': makeMe(ADMIN_PERMISSIONS),
      'GET /api/spaces': page([]),
      'GET /api/admin/users': page([lea]),
      'GET /api/admin/groups/:id': {
        id: 'g1',
        name: 'Redaktion',
        description: 'Texte',
        version: 1,
      },
      'GET /api/admin/groups/:id/members': () => page(members),
      'POST /api/admin/groups/:id/members': () => {
        members.push({ member_type: 'user', member_id: lea.id, name: lea.name })
        return { status: 204 }
      },
    })
    const { user } = await renderApp('/admin/groups/g1')
    expect(await screen.findByText('Diese Gruppe hat noch keine Mitglieder.')).toBeInTheDocument()
    await user.selectOptions(
      screen.getByLabelText('Person hinzufügen'),
      'Lea Löwe (lea@example.com)',
    )
    await user.click(screen.getByRole('button', { name: 'Hinzufügen' }))
    expect(await screen.findByRole('cell', { name: 'Lea Löwe' })).toBeInTheDocument()
    expect(api.find('POST', '/api/admin/groups/g1/members')[0]?.body).toEqual({
      member_type: 'user',
      member_id: lea.id,
    })
  })

  test('the audit log filters by action and shows who did what', async () => {
    const api = mockApi({
      'GET /api/auth/me': makeMe(ADMIN_PERMISSIONS),
      'GET /api/spaces': page([]),
      'GET /api/admin/users': page([]),
      'GET /api/admin/audit': (call) =>
        page(
          call.query.get('action') === 'space.created'
            ? [
                {
                  id: 'a1',
                  actor_type: 'user',
                  actor_id: 'u1',
                  actor_name: 'Mia Muster',
                  action: 'space.created',
                  target_type: 'space',
                  target_id: 's1',
                  details: { kind: 'team', name: 'Team Dienste' },
                  ip: '127.0.0.1',
                  created_at: '2026-11-12T10:00:00Z',
                },
              ]
            : [],
        ),
    })
    const { user } = await renderApp('/admin/audit')
    expect(await screen.findByText('Keine Einträge.')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Aktion'), 'Bereich angelegt')
    const row = (await screen.findByRole('cell', { name: 'Mia Muster' })).closest('tr')!
    expect(row).toHaveTextContent('Bereich angelegt')
    expect(row).toHaveTextContent('Art: Team, Name: Team Dienste')
    expect(api.find('GET', '/api/admin/audit').at(-1)?.query.get('action')).toBe('space.created')
  })
})
