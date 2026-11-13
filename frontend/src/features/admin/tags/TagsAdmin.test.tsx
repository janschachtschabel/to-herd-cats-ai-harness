import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { SpaceRole, Tag } from '@/lib/api'
import { apiError, makeMe, makeSpace, makeTag, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'

describe('system-wide tags', () => {
  test('without tag.manage there is no tags page and no link to it', async () => {
    const api = mockApi({
      'GET /api/auth/me': makeMe(['audit.read']),
      'GET /api/spaces': page([]),
      'GET /api/admin/audit': page([]),
    })
    await renderApp('/admin/tags')
    expect(await screen.findByRole('heading', { name: 'Seite nicht gefunden' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Tags' })).toBeNull()
    expect(api.find('GET', '/api/tags')).toEqual([])
  })

  test('an admin lists, creates, renames, recolours and deletes system tags', async () => {
    let tags: Tag[] = []
    const api = mockApi({
      'GET /api/auth/me': makeMe(['tag.manage']),
      'GET /api/spaces': page([]),
      'GET /api/tags': () => page(tags),
      'POST /api/tags': (call) => {
        const created = makeTag({ ...(call.body as Partial<Tag>) })
        tags = [...tags, created]
        return { status: 201, body: created }
      },
      'PATCH /api/tags/:id': (call, params) => {
        const body = call.body as Partial<Tag>
        tags = tags.map((t) => (t.id === params.id ? { ...t, ...body, version: t.version + 1 } : t))
        return tags.find((t) => t.id === params.id)
      },
      'DELETE /api/tags/:id': (_call, params) => {
        tags = tags.filter((t) => t.id !== params.id)
        return { status: 204 }
      },
    })
    const { user } = await renderApp('/admin')
    expect(await screen.findByRole('heading', { name: 'Tags', level: 1 })).toBeInTheDocument()
    expect(await screen.findByText('Noch keine systemweiten Tags.')).toBeInTheDocument()
    expect(api.find('GET', '/api/tags')[0]?.query.get('system')).toBe('true')

    await user.click(screen.getByRole('button', { name: 'Neuer Tag' }))
    let dialog = await screen.findByRole('dialog', { name: 'Neuer Tag' })
    await user.type(within(dialog).getByLabelText('Name'), 'Wichtig')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(api.find('POST', '/api/tags')[0]?.body).toEqual({ name: 'Wichtig', color: '#64748b' })
    expect(await screen.findByRole('cell', { name: 'Wichtig' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Tag „Wichtig“ bearbeiten' }))
    dialog = await screen.findByRole('dialog', { name: 'Tag bearbeiten' })
    const name = within(dialog).getByLabelText('Name')
    await user.clear(name)
    await user.type(name, 'Dringend')
    const colour = within(dialog).getByLabelText('Farbe')
    await user.clear(colour)
    await user.type(colour, '#DC2626')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(api.find('PATCH', `/api/tags/${tags[0]!.id}`)[0]?.body).toEqual({
      name: 'Dringend',
      color: '#dc2626',
      version: 1,
    })
    expect(await screen.findByRole('cell', { name: 'Dringend' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Tag „Dringend“ löschen' }))
    dialog = await screen.findByRole('dialog', { name: 'Tag löschen?' })
    await user.click(within(dialog).getByRole('button', { name: 'Löschen' }))
    expect(await screen.findByText('Noch keine systemweiten Tags.')).toBeInTheDocument()
  })

  test('a name already taken and a stale version are explained; reload takes the new version', async () => {
    let tag = makeTag({ name: 'Alt', version: 1 })
    const api = mockApi({
      'GET /api/auth/me': makeMe(['tag.manage']),
      'GET /api/spaces': page([]),
      'GET /api/tags': () => page([tag]),
      'POST /api/tags': apiError(409, 'tags.name_taken'),
      'PATCH /api/tags/:id': (call) => {
        const body = call.body as { version: number }
        if (body.version !== 2) {
          tag = { ...tag, version: 2 }
          return apiError(409, 'tags.version_conflict')
        }
        tag = { ...tag, name: 'Neu', version: 3 }
        return tag
      },
    })
    const { user } = await renderApp('/admin/tags')
    await user.click(await screen.findByRole('button', { name: 'Neuer Tag' }))
    let dialog = await screen.findByRole('dialog', { name: 'Neuer Tag' })
    await user.type(within(dialog).getByLabelText('Name'), 'alt')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    expect(
      await within(dialog).findByText('Einen Tag mit diesem Namen gibt es schon.'),
    ).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Abbrechen' }))

    await user.click(screen.getByRole('button', { name: 'Tag „Alt“ bearbeiten' }))
    dialog = await screen.findByRole('dialog', { name: 'Tag bearbeiten' })
    await user.clear(within(dialog).getByLabelText('Name'))
    await user.type(within(dialog).getByLabelText('Name'), 'Neu')
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await user.click(await within(dialog).findByRole('button', { name: 'Aktuelle Fassung laden' }))
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(api.find('PATCH', `/api/tags/${tag.id}`).map((c) => c.body)).toEqual([
      { name: 'Neu', color: '#2563eb', version: 1 },
      { name: 'Neu', color: '#2563eb', version: 2 },
    ])
  })

  test('the list shows an error with a retry', async () => {
    let fail = true
    mockApi({
      'GET /api/auth/me': makeMe(['tag.manage']),
      'GET /api/spaces': page([]),
      'GET /api/tags': () => (fail ? apiError(500, 'internal') : page([makeTag({ name: 'Da' })])),
    })
    const { user } = await renderApp('/admin/tags')
    const retry = await screen.findByRole('button', { name: 'Erneut versuchen' })
    fail = false
    await user.click(retry)
    expect(await screen.findByRole('cell', { name: 'Da' })).toBeInTheDocument()
  })
})

describe('tags of a space', () => {
  const space = makeSpace({ name: 'Handbuch' })
  const system = makeTag({ name: 'System' })
  const own = makeTag({ name: 'Team', space_id: space.id, color: '#16a34a' })

  function spaceApi(role: SpaceRole) {
    const roleSpace = { ...space, my_role: role }
    return mockApi({
      'GET /api/auth/me': makeMe([]),
      'GET /api/spaces': page([roleSpace]),
      'GET /api/spaces/:id': roleSpace,
      'GET /api/spaces/:id/pages/tree': page([]),
      'GET /api/spaces/:id/members': page([]),
      'GET /api/tags': page([own, system]),
      'DELETE /api/tags/:id': { status: 204 },
    })
  }

  test('a moderator manages only the space’s own tags in the settings', async () => {
    const api = spaceApi('moderator')
    const { user } = await renderApp(`/spaces/${space.id}/settings`)
    const section = await screen.findByRole('region', { name: 'Tags dieses Bereichs' })
    expect(await within(section).findByRole('cell', { name: 'Team' })).toBeInTheDocument()
    expect(within(section).queryByRole('cell', { name: 'System' })).toBeNull()
    await user.click(within(section).getByRole('button', { name: 'Tag „Team“ löschen' }))
    const dialog = await screen.findByRole('dialog', { name: 'Tag löschen?' })
    await user.click(within(dialog).getByRole('button', { name: 'Löschen' }))
    await waitFor(() => expect(api.find('DELETE', `/api/tags/${own.id}`)).toHaveLength(1))
  })

  test('an editor does not see the space tags section', async () => {
    spaceApi('editor')
    await renderApp(`/spaces/${space.id}/settings`)
    expect(await screen.findByRole('heading', { name: 'Mitglieder' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Tags dieses Bereichs' })).toBeNull()
  })
})
