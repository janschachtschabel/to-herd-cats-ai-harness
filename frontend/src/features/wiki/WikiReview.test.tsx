import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { SpaceRole, WikiPage } from '@/lib/api'
import { apiError, makeMe, makePage, makeSpace, mockApi, nodeOf, page } from '@/test/api'
import { renderApp } from '@/test/render'

const space = makeSpace({ name: 'Handbuch', review_interval_days: 30 })
const due = makePage({
  space_id: space.id,
  title: 'Urlaub',
  slug: 'urlaub',
  path: 'urlaub',
  reviewed_at: '2026-10-01T10:00:00Z',
  review_due: true,
})
const fresh = makePage({
  space_id: space.id,
  title: 'Anreise',
  slug: 'anreise',
  path: 'anreise',
  sort_order: 1,
})

function reviewApi(role: SpaceRole, extra = {}, spaceOverrides = {}) {
  const roleSpace = { ...space, my_role: role, ...spaceOverrides }
  const pages: WikiPage[] = [due, fresh]
  return mockApi({
    'GET /api/auth/me': makeMe([]),
    'GET /api/spaces': page([roleSpace]),
    'GET /api/spaces/:id': roleSpace,
    'GET /api/spaces/:id/pages/tree': (call) =>
      page(
        pages.filter((p) => call.query.get('review_due') !== 'true' || p.review_due).map(nodeOf),
      ),
    'GET /api/spaces/:id/pages/by-path': (call) =>
      pages.find((p) => p.path === call.query.get('path')) ?? apiError(404, 'page.not_found'),
    'GET /api/tags': page([]),
    'GET /api/pages/:id/attachments': page([]),
    'GET /api/pages/:id/versions': page([]),
    ...extra,
  })
}

describe('pages whose review is due', () => {
  test('an editor sees the mark with the last review and marks the page as reviewed', async () => {
    const api = reviewApi('editor', {
      'POST /api/pages/:id/reviewed': () => ({
        ...due,
        reviewed_at: '2026-11-14T09:00:00Z',
        review_due: false,
      }),
    })
    const { user } = await renderApp(`/spaces/${space.id}/p/urlaub`)
    const mark = await screen.findByRole('region', { name: 'Prüfung fällig' })
    expect(
      within(mark).getByText(
        'Zuletzt geprüft am 01.10.2026. Der Bereich verlangt eine Prüfung alle 30 Tage.',
      ),
    ).toBeInTheDocument()
    await user.click(within(mark).getByRole('button', { name: 'Als geprüft markieren' }))
    await waitFor(() => expect(api.find('POST', `/api/pages/${due.id}/reviewed`)).toHaveLength(1))
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Prüfung fällig' })).toBeNull())
  })

  test('a viewer sees the mark but no button; a page not due has no mark', async () => {
    reviewApi('viewer')
    const { router } = await renderApp(`/spaces/${space.id}/p/urlaub`)
    const mark = await screen.findByRole('region', { name: 'Prüfung fällig' })
    expect(within(mark).queryByRole('button')).toBeNull()

    await router.navigate({
      to: '/spaces/$spaceId/p/$',
      params: { spaceId: space.id, _splat: 'anreise' },
    })
    expect(await screen.findByRole('heading', { level: 2, name: 'Anreise' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Prüfung fällig' })).toBeNull()
  })

  test('a failed mark is worded', async () => {
    reviewApi('editor', {
      'POST /api/pages/:id/reviewed': apiError(409, 'page.not_published'),
    })
    const { user } = await renderApp(`/spaces/${space.id}/p/urlaub`)
    const mark = await screen.findByRole('region', { name: 'Prüfung fällig' })
    await user.click(within(mark).getByRole('button', { name: 'Als geprüft markieren' }))
    expect(
      await within(mark).findByText('Nur veröffentlichte Seiten werden geprüft.'),
    ).toBeInTheDocument()
  })

  test('the tree marks due pages and filters to them', async () => {
    const api = reviewApi('viewer')
    const { user } = await renderApp(`/spaces/${space.id}`)
    const tree = await screen.findByRole('tree', { name: 'Seiten' })
    const item = within(tree).getByRole('treeitem', { name: /Urlaub/ })
    expect(within(item).getByRole('img', { name: 'Prüfung fällig' })).toBeInTheDocument()
    const other = within(tree).getByRole('treeitem', { name: /Anreise/ })
    expect(within(other).queryByRole('img', { name: 'Prüfung fällig' })).toBeNull()

    await user.click(screen.getByRole('checkbox', { name: 'Nur Seiten mit fälliger Prüfung' }))
    const filtered = await screen.findByRole('tree', { name: 'Seiten mit fälliger Prüfung' })
    expect(within(filtered).getAllByRole('treeitem')).toHaveLength(1)
    expect(
      api.calls.some((c) => c.path.endsWith('/pages/tree') && c.query.get('review_due') === 'true'),
    ).toBe(true)
  })

  test('without an interval there is no filter', async () => {
    reviewApi('viewer', {}, { review_interval_days: null })
    await renderApp(`/spaces/${space.id}`)
    await screen.findByRole('tree', { name: 'Seiten' })
    expect(screen.queryByRole('checkbox', { name: 'Nur Seiten mit fälliger Prüfung' })).toBeNull()
  })

  test('the filter with nothing due says so', async () => {
    reviewApi('viewer', {
      'GET /api/spaces/:id/pages/tree': (call: { query: URLSearchParams }) =>
        page(call.query.get('review_due') === 'true' ? [] : [nodeOf(fresh)]),
    })
    const { user } = await renderApp(`/spaces/${space.id}`)
    await user.click(
      await screen.findByRole('checkbox', { name: 'Nur Seiten mit fälliger Prüfung' }),
    )
    expect(await screen.findByText('Keine Seite ist zur Prüfung fällig.')).toBeInTheDocument()
  })
})
