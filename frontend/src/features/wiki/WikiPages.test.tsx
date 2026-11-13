import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { SpaceRole, WikiPage } from '@/lib/api'
import { apiError, makeMe, makePage, makeSpace, mockApi, nodeOf, page } from '@/test/api'
import { renderApp } from '@/test/render'

const me = makeMe([])
const space = makeSpace({ name: 'Handbuch', my_role: 'viewer' })
const root = makePage({ space_id: space.id, title: 'Start', slug: 'start', path: 'start' })
const child = makePage({
  space_id: space.id,
  parent_id: root.id,
  title: 'Urlaub',
  slug: 'urlaub',
  path: 'start/urlaub',
  sort_order: 1,
  content_md: '# Urlaub\n\nSiehe [[Start]].',
})
const sibling = makePage({
  space_id: space.id,
  parent_id: root.id,
  title: 'Anreise',
  slug: 'anreise',
  path: 'start/anreise',
  sort_order: 0,
})

function wikiApi(role: SpaceRole, pages: WikiPage[] = [root, child, sibling], extra = {}) {
  const roleSpace = { ...space, my_role: role }
  return mockApi({
    'GET /api/auth/me': me,
    'GET /api/spaces': page([roleSpace]),
    'GET /api/spaces/:id': roleSpace,
    'GET /api/spaces/:id/pages/tree': page(pages.map(nodeOf)),
    'GET /api/spaces/:id/pages/by-path': (call) =>
      pages.find((p) => p.path === call.query.get('path')) ?? apiError(404, 'page.not_found'),
    'GET /api/tags': page([]),
    'GET /api/pages/:id/attachments': page([]),
    ...extra,
  })
}

describe('wiki', () => {
  test('the tree nests the flat list and is operable by keyboard', async () => {
    wikiApi('viewer')
    const { router, user } = await renderApp(`/spaces/${space.id}`)
    const tree = await screen.findByRole('tree', { name: 'Seiten' })
    const start = within(tree).getByRole('treeitem', { name: 'Start' })
    expect(start).toHaveAttribute('aria-expanded', 'true')
    const children = within(start).getAllByRole('treeitem')
    // Siblings by sort order, not by path.
    expect(children.map((item) => item.getAttribute('aria-labelledby'))).toEqual([
      `page-tree-${sibling.id}`,
      `page-tree-${child.id}`,
    ])
    expect(children[0]).toHaveAttribute('aria-level', '2')

    start.focus()
    await user.keyboard('{ArrowLeft}')
    expect(start).toHaveAttribute('aria-expanded', 'false')
    expect(within(start).queryAllByRole('treeitem')).toEqual([])
    await user.keyboard('{ArrowRight}{ArrowRight}{ArrowDown}')
    expect(within(start).getByRole('treeitem', { name: 'Urlaub' })).toHaveFocus()
    await user.keyboard('{Enter}')
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/spaces/${space.id}/p/start/urlaub`),
    )
    expect(await screen.findByRole('heading', { level: 2, name: 'Urlaub' })).toBeInTheDocument()
    // Breadcrumbs and the resolved wiki link lead to the parent.
    const crumbs = screen.getByRole('navigation', { name: 'Seitenpfad' })
    expect(within(crumbs).getByRole('link', { name: 'Start' })).toBeInTheDocument()
    const article = screen.getByRole('article')
    expect(within(article).getAllByRole('link', { name: 'Start' })).toHaveLength(2)
  })

  test('viewer sees no edit actions', async () => {
    wikiApi('viewer')
    const { user } = await renderApp(`/spaces/${space.id}/p/start/urlaub`)
    await screen.findByRole('heading', { level: 2, name: 'Urlaub' })
    for (const name of ['Bearbeiten', 'Veröffentlichen', 'Neue Seite', 'Papierkorb']) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
      expect(screen.queryByRole('link', { name })).not.toBeInTheDocument()
    }
    expect(screen.queryByRole('button', { name: 'Datei hochladen' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Weitere Aktionen' }))
    const menu = await screen.findByRole('menu')
    expect(within(menu).getByRole('menuitem', { name: 'Versionen' })).toBeInTheDocument()
    for (const name of ['Umbenennen', 'Verschieben', 'Tags', 'In den Papierkorb']) {
      expect(within(menu).queryByRole('menuitem', { name })).not.toBeInTheDocument()
    }
  })

  test('an editor edits and publishes own drafts, a moderator also trashes', async () => {
    const draft = {
      ...child,
      status: 'draft' as const,
      created_by: { type: 'user' as const, id: me.user.id },
    }
    wikiApi('editor', [root, draft])
    const { user } = await renderApp(`/spaces/${space.id}/p/start/urlaub`)
    await screen.findByRole('heading', { level: 2, name: 'Urlaub' })
    expect(screen.getByRole('link', { name: 'Bearbeiten' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Veröffentlichen' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Neue Seite' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Papierkorb' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Weitere Aktionen' }))
    const menu = await screen.findByRole('menu')
    expect(within(menu).getByRole('menuitem', { name: 'Verschieben' })).toBeInTheDocument()
    expect(within(menu).queryByRole('menuitem', { name: 'In den Papierkorb' })).toBeNull()
  })

  test("an editor cannot publish someone else's draft; a moderator can", async () => {
    const draft = { ...child, status: 'draft' as const }
    wikiApi('editor', [root, draft])
    await renderApp(`/spaces/${space.id}/p/start/urlaub`)
    await screen.findByRole('heading', { level: 2, name: 'Urlaub' })
    expect(screen.queryByRole('button', { name: 'Veröffentlichen' })).not.toBeInTheDocument()
  })

  test('publishing below a draft parent says why it cannot', async () => {
    const draft = { ...child, status: 'draft' as const }
    const api = wikiApi('moderator', [root, draft], {
      'POST /api/pages/:id/publish': apiError(409, 'page.parent_draft'),
    })
    const { user } = await renderApp(`/spaces/${space.id}/p/start/urlaub`)
    await user.click(await screen.findByRole('button', { name: 'Veröffentlichen' }))
    expect(
      await screen.findByText(
        'Die übergeordnete Seite ist noch ein Entwurf. Veröffentliche zuerst sie.',
      ),
    ).toBeInTheDocument()
    expect(api.find('POST', `/api/pages/${draft.id}/publish`)[0]?.body).toEqual({
      version: draft.version,
    })
  })

  test('a stale version on publish refetches the page and says so', async () => {
    let current = { ...child, status: 'draft' as const }
    const api = wikiApi('moderator', [root, current], {
      'GET /api/spaces/:id/pages/by-path': () => current,
      'POST /api/pages/:id/publish': (call: { body: unknown }) => {
        if ((call.body as { version: number }).version !== 2) {
          current = { ...current, version: 2 }
          return apiError(409, 'page.version_conflict')
        }
        return { ...current, status: 'published', version: 3 }
      },
    })
    const { user } = await renderApp(`/spaces/${space.id}/p/start/urlaub`)
    await user.click(await screen.findByRole('button', { name: 'Veröffentlichen' }))
    expect(await screen.findByText(/Die aktuelle Fassung ist geladen/)).toBeInTheDocument()
    await waitFor(() =>
      expect(api.find('GET', `/api/spaces/${space.id}/pages/by-path`)).toHaveLength(2),
    )
    await user.click(screen.getByRole('button', { name: 'Veröffentlichen' }))
    await waitFor(() =>
      expect(api.find('POST', `/api/pages/${current.id}/publish`).map((c) => c.body)).toEqual([
        { version: 1 },
        { version: 2 },
      ]),
    )
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Veröffentlichen' })).toBeNull(),
    )
  })

  test('creating a page opens it in the editor', async () => {
    const created = makePage({
      space_id: space.id,
      title: 'Neu',
      slug: 'neu',
      path: 'neu',
      status: 'draft',
      content_md: '',
    })
    const pages = [root]
    const api = wikiApi('editor', pages, {
      'POST /api/spaces/:id/pages': () => (pages.push(created), { status: 201, body: created }),
    })
    const { router, user } = await renderApp(`/spaces/${space.id}`)
    await user.click(await screen.findByRole('button', { name: 'Neue Seite' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Titel'), 'Neu')
    await user.selectOptions(within(dialog).getByLabelText('Übergeordnete Seite'), root.id)
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/spaces/${space.id}/p/neu`))
    expect(router.state.location.search).toEqual({ view: 'edit' })
    expect(api.find('POST', `/api/spaces/${space.id}/pages`)[0]?.body).toEqual({
      title: 'Neu',
      parent_id: root.id,
      content_md: '',
    })
    expect(await screen.findByRole('form', { name: 'Seite bearbeiten' })).toBeInTheDocument()
  })

  test('moving a page sends parent and position and follows the new path', async () => {
    const moved = { ...sibling, parent_id: null, path: 'anreise', version: 2 }
    const api = wikiApi('editor', [root, child, sibling], {
      'POST /api/pages/:id/move': moved,
    })
    const { router, user } = await renderApp(`/spaces/${space.id}/p/start/anreise`)
    await user.click(await screen.findByRole('button', { name: 'Weitere Aktionen' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Verschieben' }))
    const dialog = await screen.findByRole('dialog')
    const parent = within(dialog).getByLabelText('Übergeordnete Seite')
    // Not below itself: the page is not offered as its own parent.
    expect(within(parent).queryByRole('option', { name: /Anreise/ })).toBeNull()
    await user.selectOptions(parent, '')
    await user.selectOptions(within(dialog).getByLabelText('Stelle'), 'Nach „Start“')
    await user.click(within(dialog).getByRole('button', { name: 'Verschieben' }))
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/spaces/${space.id}/p/anreise`),
    )
    expect(api.find('POST', `/api/pages/${sibling.id}/move`)[0]?.body).toEqual({
      parent_id: null,
      position: 1,
      version: 1,
    })
  })
})
