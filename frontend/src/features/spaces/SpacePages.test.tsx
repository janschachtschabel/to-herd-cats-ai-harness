import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { Space, SpaceMember } from '@/lib/api'
import {
  ADMIN_PERMISSIONS,
  apiError,
  makeEntry,
  makeMe,
  makeSpace,
  mockApi,
  page,
} from '@/test/api'
import { renderApp } from '@/test/render'

describe('spaces', () => {
  test('admin creates a team space and adds a group as editor', async () => {
    const me = makeMe(ADMIN_PERMISSIONS)
    const created = makeSpace({ name: 'Team Dienste', my_role: 'admin' })
    const group = makeEntry({ type: 'group', name: 'Redaktion' })
    const listed: Space[] = []
    const members: SpaceMember[] = [
      { member_type: 'user', member_id: me.user.id, role: 'admin', name: 'Mia Muster' },
    ]
    const api = mockApi({
      'GET /api/auth/me': me,
      'GET /api/spaces': () => page(listed),
      'POST /api/spaces': () => (listed.push(created), { status: 201, body: created }),
      'GET /api/spaces/:id': created,
      'GET /api/spaces/:id/members': () => page(members),
      'PUT /api/spaces/:id/members': (call) => {
        const member = { ...(call.body as Omit<SpaceMember, 'name'>), name: 'Redaktion' }
        members.push(member)
        return member
      },
      'GET /api/directory': (call) =>
        page(
          [makeEntry({ name: 'Lea Löwe' }), group].filter((e) =>
            e.name.includes(call.query.get('q') ?? ''),
          ),
        ),
    })
    const { router, user } = await renderApp('/spaces')

    await user.click(await screen.findByRole('button', { name: 'Bereich anlegen' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByLabelText(/^Team/))
    await user.type(within(dialog).getByLabelText('Name'), 'Team Dienste')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))

    await waitFor(() => expect(router.state.location.pathname).toBe(`/spaces/${created.id}`))
    // The sidebar lists the new space without a reload.
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
    expect(await within(nav).findByRole('link', { name: 'Team Dienste' })).toBeInTheDocument()
    expect(api.find('POST', '/api/spaces')[0]?.body).toEqual({
      kind: 'team',
      name: 'Team Dienste',
      description: null,
      icon: null,
    })

    const form = await screen.findByRole('form', { name: 'Mitglied hinzufügen' })
    await user.type(within(form).getByRole('combobox', { name: 'Person oder Gruppe' }), 'Red')
    await user.click(await screen.findByRole('option', { name: /Redaktion/ }))
    await user.selectOptions(within(form).getByLabelText('Rolle'), 'Autor')
    await user.click(within(form).getByRole('button', { name: 'Hinzufügen' }))

    await waitFor(() =>
      expect(api.find('PUT', `/api/spaces/${created.id}/members`)[0]?.body).toEqual({
        member_type: 'group',
        member_id: group.id,
        role: 'editor',
      }),
    )
    const row = (await screen.findByText('Redaktion', { selector: 'td span' })).closest('tr')!
    expect(within(row).getByLabelText('Rolle von Redaktion')).toHaveValue('editor')
  })

  test('a space admin without administration rights finds people in the directory', async () => {
    const space = makeSpace({ kind: 'team', name: 'Projekt Apfel', my_role: 'admin' })
    const lea = makeEntry({ name: 'Lea Löwe' })
    const present = makeEntry({ name: 'Leo Dabei' })
    const otto = makeEntry({ name: 'Otto Anders' })
    const api = mockApi({
      'GET /api/auth/me': makeMe(['directory.read', 'space.create']),
      'GET /api/spaces': page([space]),
      'GET /api/spaces/:id': space,
      'GET /api/spaces/:id/members': page([
        { member_type: 'user', member_id: present.id, role: 'viewer', name: present.name },
      ]),
      'GET /api/directory': (call) =>
        call.query.get('q') ? page([present, lea]) : page([present, otto]),
      'PUT /api/spaces/:id/members': (call) => ({ ...(call.body as object), name: lea.name }),
    })
    const { user } = await renderApp(`/spaces/${space.id}`)
    const form = await screen.findByRole('form', { name: 'Mitglied hinzufügen' })
    expect(screen.queryByText(/nur die Verwaltung/)).not.toBeInTheDocument()

    const box = within(form).getByRole('combobox', { name: 'Person oder Gruppe' })
    await user.click(box)
    expect(await screen.findByRole('option', { name: /Otto Anders/ })).toBeInTheDocument()
    await user.type(box, 'Le')
    // Until the search for "Le" has answered, no stale result can be picked.
    expect(screen.queryByRole('option', { name: /Otto Anders/ })).not.toBeInTheDocument()
    const listbox = await screen.findByRole('listbox')
    expect(await within(listbox).findByRole('option', { name: /Lea Löwe/ })).toBeInTheDocument()
    // Members already in the space are not offered again.
    expect(within(listbox).queryByRole('option', { name: /Leo Dabei/ })).not.toBeInTheDocument()
    // Focus lists everyone; typing is debounced: one search for "Le", none for "L".
    await waitFor(() =>
      expect(api.find('GET', '/api/directory').map((c) => c.query.get('q'))).toEqual(['', 'Le']),
    )

    await user.keyboard('{ArrowDown}{Enter}')
    expect(box).toHaveValue('Lea Löwe')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    await user.click(within(form).getByRole('button', { name: 'Hinzufügen' }))
    await waitFor(() =>
      expect(api.find('PUT', `/api/spaces/${space.id}/members`)[0]?.body).toEqual({
        member_type: 'user',
        member_id: lea.id,
        role: 'viewer',
      }),
    )
    expect(api.find('GET', '/api/admin/users')).toEqual([])
    await waitFor(() => expect(box).toHaveValue(''))
  })

  test('the picker says when nobody matches and closes on Escape', async () => {
    const space = makeSpace({ kind: 'team', my_role: 'admin' })
    mockApi({
      'GET /api/auth/me': makeMe(['directory.read']),
      'GET /api/spaces': page([space]),
      'GET /api/spaces/:id': space,
      'GET /api/spaces/:id/members': page([]),
      'GET /api/directory': page([]),
    })
    const { user } = await renderApp(`/spaces/${space.id}`)
    const box = await screen.findByRole('combobox', { name: 'Person oder Gruppe' })
    await user.type(box, 'zzz')
    expect(await screen.findByText('Niemand gefunden.')).toBeInTheDocument()
    expect(box).toHaveAttribute('aria-expanded', 'true')
    await user.keyboard('{Escape}')
    expect(box).toHaveAttribute('aria-expanded', 'false')
  })

  test('without directory.read a space admin is told why nobody can be added', async () => {
    const space = makeSpace({ kind: 'team', my_role: 'admin' })
    const api = mockApi({
      'GET /api/auth/me': makeMe([]),
      'GET /api/spaces': page([space]),
      'GET /api/spaces/:id': space,
      'GET /api/spaces/:id/members': page([]),
    })
    await renderApp(`/spaces/${space.id}`)
    expect(await screen.findByText(/Gäste können/)).toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Person oder Gruppe' })).not.toBeInTheDocument()
    expect(api.find('GET', '/api/directory')).toEqual([])
  })

  test('the create form checks the limits the API declares', async () => {
    mockApi({ 'GET /api/auth/me': makeMe(['space.create']), 'GET /api/spaces': page([]) })
    const { user } = await renderApp('/spaces')
    await user.click(await screen.findByRole('button', { name: 'Bereich anlegen' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Name'), 'x'.repeat(121))
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    expect(await within(dialog).findByText('Höchstens 120 Zeichen.')).toBeInTheDocument()
    expect(within(dialog).getByLabelText('Name')).toHaveAttribute('aria-invalid', 'true')
  })

  test('409 on stale version shows reload hint and keeps the form', async () => {
    let current: Space = makeSpace({ name: 'Projekt Apfel', version: 3 })
    const api = mockApi({
      'GET /api/auth/me': makeMe(['space.create']),
      'GET /api/spaces': page([current]),
      'GET /api/spaces/:id': () => current,
      'GET /api/spaces/:id/members': page([]),
      'PATCH /api/spaces/:id': (call) => {
        const body = call.body as { name: string; version: number }
        if (body.version !== current.version) return apiError(409, 'spaces.version_conflict')
        current = { ...current, name: body.name, version: current.version + 1 }
        return current
      },
    })
    const { user } = await renderApp(`/spaces/${current.id}`)
    await user.click(await screen.findByRole('button', { name: 'Einstellungen' }))
    const dialog = await screen.findByRole('dialog')
    current = { ...current, description: 'von jemand anderem', version: 4 } // someone else saved
    const name = within(dialog).getByLabelText('Name')
    await user.clear(name)
    await user.type(name, 'Projekt Birne')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))

    expect(await within(dialog).findByText(/inzwischen geändert/)).toBeInTheDocument()
    expect(name).toHaveValue('Projekt Birne')

    await user.click(within(dialog).getByRole('button', { name: 'Aktuelle Fassung laden' }))
    await waitFor(() =>
      expect(within(dialog).queryByText(/inzwischen geändert/)).not.toBeInTheDocument(),
    )
    expect(name).toHaveValue('Projekt Birne')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    const patches = api.find('PATCH', `/api/spaces/${current.id}`).map((c) => c.body)
    expect(patches).toMatchObject([
      { name: 'Projekt Birne', version: 3 },
      { name: 'Projekt Birne', version: 4 },
    ])
  })

  test('personal space shows no member editor', async () => {
    const me = makeMe(ADMIN_PERMISSIONS)
    const mine = makeSpace({ kind: 'personal', name: 'Mia Muster', owner_user_id: me.user.id })
    mockApi({
      'GET /api/auth/me': me,
      'GET /api/spaces': page([mine]),
      'GET /api/spaces/:id': mine,
      'GET /api/spaces/:id/members': page([
        { member_type: 'user', member_id: me.user.id, role: 'admin', name: 'Mia Muster' },
      ]),
    })
    await renderApp(`/spaces/${mine.id}`)
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Mein Bereich' }),
    ).toBeInTheDocument()
    expect(await screen.findByRole('cell', { name: /Mia Muster/ })).toBeInTheDocument()
    expect(screen.getByText(/gehört genau einer Person/)).toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Mitglied hinzufügen' })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /entfernen/ })).not.toBeInTheDocument()
  })

  test('a reader sees members and roles but cannot change them', async () => {
    const space = makeSpace({ kind: 'open', name: 'Handbuch', my_role: 'viewer' })
    mockApi({
      'GET /api/auth/me': makeMe(['space.create']),
      'GET /api/spaces': page([space]),
      'GET /api/spaces/:id': space,
      'GET /api/spaces/:id/members': page([
        { member_type: 'group', member_id: 'g', role: 'editor', name: 'Redaktion' },
      ]),
    })
    await renderApp(`/spaces/${space.id}`)
    expect(await screen.findByRole('cell', { name: 'Autor' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Einstellungen' })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })

  test('the list groups spaces by kind and loads more on request', async () => {
    const me = makeMe(['space.create'])
    const api = mockApi({
      'GET /api/auth/me': me,
      'GET /api/spaces': (call) =>
        call.query.get('cursor') === 'next'
          ? page([makeSpace({ kind: 'team', name: 'Später geladen' })])
          : page(
              [
                makeSpace({ kind: 'team', name: 'Team Dienste', my_role: 'editor' }),
                makeSpace({ kind: 'open', name: 'Handbuch', my_role: 'viewer' }),
                makeSpace({ kind: 'personal', name: 'Mia', owner_user_id: me.user.id }),
              ],
              'next',
            ),
    })
    const { user } = await renderApp('/spaces')
    const main = screen.getByRole('main')
    const headings = within(main)
      .getAllByRole('heading', { level: 2 })
      .map((h) => h.textContent)
    expect(headings).toEqual(['Offene Bereiche', 'Team-Bereiche', 'Persönliche Bereiche'])
    expect(within(main).getByRole('link', { name: /Mein Bereich/ })).toBeInTheDocument()
    expect(within(main).getByRole('link', { name: /Team Dienste.*Autor/ })).toBeInTheDocument()

    await user.click(within(main).getByRole('button', { name: 'Mehr laden' }))
    expect(await within(main).findByText('Später geladen')).toBeInTheDocument()
    expect(api.find('GET', '/api/spaces').at(-1)?.query.get('cursor')).toBe('next')
    expect(within(main).queryByRole('button', { name: 'Mehr laden' })).not.toBeInTheDocument()
  })

  test('without space.create there is no create button; an empty list says so', async () => {
    mockApi({ 'GET /api/auth/me': makeMe([]), 'GET /api/spaces': page([]) })
    await renderApp('/spaces')
    expect(await screen.findByText('Noch keine Bereiche.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Bereich anlegen' })).not.toBeInTheDocument()
  })

  test('an unknown space shows the error with its trace id', async () => {
    mockApi({
      'GET /api/auth/me': makeMe([]),
      'GET /api/spaces': page([]),
      'GET /api/spaces/:id': apiError(404, 'space.not_found'),
    })
    await renderApp('/spaces/nope')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Diesen Bereich gibt es nicht.')
    expect(alert).toHaveTextContent('Trace-ID 4bf92f3577b34da6a3ce929d0e0e4736')
  })
})
