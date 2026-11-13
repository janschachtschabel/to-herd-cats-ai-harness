import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { SpaceRole, WikiPage } from '@/lib/api'
import { apiError, makeMe, makePage, makeSpace, makeTag, mockApi, nodeOf, page } from '@/test/api'
import { renderApp } from '@/test/render'

const me = makeMe([])
const space = makeSpace({ name: 'Handbuch', my_role: 'viewer' })
const howto = makeTag({ name: 'Anleitung', color: '#2563eb' })
const team = makeTag({ name: 'Team', color: '#16a34a', space_id: space.id })
const root = makePage({ space_id: space.id, title: 'Start', slug: 'start', path: 'start' })
const child = makePage({
  space_id: space.id,
  parent_id: root.id,
  title: 'Urlaub',
  slug: 'urlaub',
  path: 'start/urlaub',
  tags: [howto.id],
})
const other = makePage({ space_id: space.id, title: 'Reisen', slug: 'reisen', path: 'reisen' })

function tagsApi(role: SpaceRole, pages: WikiPage[] = [root, child, other], extra = {}) {
  const roleSpace = { ...space, my_role: role }
  return mockApi({
    'GET /api/auth/me': me,
    'GET /api/spaces': page([roleSpace]),
    'GET /api/spaces/:id': roleSpace,
    // The server filters by `?tag=`; the mock does what the endpoint does.
    'GET /api/spaces/:id/pages/tree': (call) => {
      const tag = call.query.get('tag')
      return page(pages.filter((p) => !tag || p.tags.includes(tag)).map(nodeOf))
    },
    'GET /api/spaces/:id/pages/by-path': (call) =>
      pages.find((p) => p.path === call.query.get('path')) ?? apiError(404, 'page.not_found'),
    'GET /api/tags': page([howto, team]),
    'GET /api/pages/:id/attachments': page([]),
    ...extra,
  })
}

describe('tags in the wiki', () => {
  test('the tree filters by tag through the server and the filter can be cleared', async () => {
    const api = tagsApi('viewer')
    const { user } = await renderApp(`/spaces/${space.id}`)
    const tree = await screen.findByRole('tree', { name: 'Seiten' })
    expect(within(tree).getAllByRole('treeitem')).toHaveLength(3)

    await user.selectOptions(screen.getByLabelText('Nach Tag filtern'), 'Anleitung')
    const filtered = await screen.findByRole('tree', { name: 'Seiten mit dem Tag „Anleitung“' })
    expect(
      within(filtered)
        .getAllByRole('treeitem')
        .map((i) => i.textContent),
    ).toEqual(['Urlaub'])
    const tagged = api.calls.filter((c) => c.query.get('tag') === howto.id)
    expect(tagged.length).toBeGreaterThan(0)

    await user.selectOptions(screen.getByLabelText('Nach Tag filtern'), 'Team')
    expect(await screen.findByText('Keine Seite trägt diesen Tag.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Filter aufheben' }))
    const full = await screen.findByRole('tree', { name: 'Seiten' })
    expect(within(full).getAllByRole('treeitem')).toHaveLength(3)
  })

  test('a viewer sees the page tags, may filter by one, but cannot edit them', async () => {
    tagsApi('viewer')
    const { user } = await renderApp(`/spaces/${space.id}/p/start/urlaub`)
    await screen.findByRole('heading', { level: 2, name: 'Urlaub' })
    expect(screen.queryByRole('button', { name: 'Tags bearbeiten' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Seiten mit dem Tag „Anleitung“' }))
    expect(
      await screen.findByRole('tree', { name: 'Seiten mit dem Tag „Anleitung“' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Nach Tag filtern')).toHaveValue(howto.id)
  })

  test('an editor changes the tags on the page itself', async () => {
    let current = { ...child }
    const api = tagsApi('editor', [root, child, other], {
      'GET /api/spaces/:id/pages/by-path': () => current,
      'PUT /api/pages/:id/tags': (call: { body: unknown }) => {
        const body = call.body as { tag_ids: string[]; version: number }
        current = { ...current, tags: body.tag_ids, version: body.version + 1 }
        return current
      },
    })
    const { user } = await renderApp(`/spaces/${space.id}/p/start/urlaub`)
    await user.click(await screen.findByRole('button', { name: 'Tags bearbeiten' }))
    const dialog = await screen.findByRole('dialog', { name: 'Tags der Seite' })
    expect(within(dialog).getByRole('checkbox', { name: 'Anleitung' })).toBeChecked()
    await user.click(within(dialog).getByRole('checkbox', { name: 'Anleitung' }))
    await user.click(within(dialog).getByRole('checkbox', { name: 'Team' }))
    await user.click(within(dialog).getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(api.find('PUT', `/api/pages/${child.id}/tags`)[0]?.body).toEqual({
      tag_ids: [team.id],
      version: child.version,
    })
    expect(
      await screen.findByRole('button', { name: 'Seiten mit dem Tag „Team“' }),
    ).toBeInTheDocument()
  })

  test('an editor adds the first tag to an untagged page', async () => {
    tagsApi('editor')
    const { user } = await renderApp(`/spaces/${space.id}/p/reisen`)
    await user.click(await screen.findByRole('button', { name: 'Tags bearbeiten' }))
    expect(await screen.findByRole('dialog', { name: 'Tags der Seite' })).toBeInTheDocument()
  })
})
