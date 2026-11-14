import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { WikiPage } from '@/lib/api'
import { apiError, makeMe, makePage, makeSpace, mockApi, nodeOf, page } from '@/test/api'
import { renderApp } from '@/test/render'
import { makeRun } from '@/test/runs'

const space = makeSpace({ name: 'Handbuch', my_role: 'editor' })
const start = makePage({ space_id: space.id, title: 'Start', slug: 'start', path: 'start' })
const folder = makePage({
  space_id: space.id,
  title: 'Agenten',
  slug: '_agenten',
  path: '_agenten',
  sort_order: -1,
})
const hilda = makePage({
  space_id: space.id,
  parent_id: folder.id,
  title: 'Hilda',
  slug: 'hilda',
  path: '_agenten/hilda',
})
const AGENT = { type: 'agent' as const, id: 'agent-hilda' }
const memory = makePage({
  space_id: space.id,
  parent_id: hilda.id,
  title: 'Gedächtnis',
  slug: 'gedaechtnis',
  path: '_agenten/hilda/gedaechtnis',
  content_md: '- Urlaub beantragt man im Portal.',
  created_by: AGENT,
  updated_by: AGENT,
})
const pages = [folder, hilda, memory, start]

function version(over: Record<string, unknown> = {}) {
  return {
    number: 2,
    title: 'Gedächtnis',
    label: null,
    change_summary: null,
    source: 'agent',
    ai: true,
    run_id: 'run-9',
    author: { type: 'agent', id: AGENT.id, name: 'Hilda' },
    created_at: '2026-11-14T09:00:00Z',
    ...over,
  }
}

function memoryApi(withAi = true, extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /api/auth/me': makeMe(withAi ? ['ai.use'] : []),
    'GET /api/spaces': page([space]),
    'GET /api/spaces/:id': space,
    'GET /api/spaces/:id/pages/tree': page(pages.map(nodeOf)),
    'GET /api/spaces/:id/proposals': page([]),
    'GET /api/spaces/:id/pages/by-path': (call) =>
      pages.find((p: WikiPage) => p.path === call.query.get('path')) ??
      apiError(404, 'page.not_found'),
    'GET /api/tags': page([]),
    'GET /api/pages/:id/attachments': page([]),
    'GET /api/pages/:id/tickets': page([]),
    'GET /api/pages/:id/versions': page([version(), version({ number: 1, run_id: 'run-8' })]),
    'GET /api/runs/:id': (_call, params) => makeRun({ id: params.id }),
    ...extra,
  })
}

describe("an agent's memory in the wiki", () => {
  test('the memory folder comes last in the tree and carries the AI mark, as its pages do', async () => {
    memoryApi()
    await renderApp(`/spaces/${space.id}`)
    const tree = await screen.findByRole('tree', { name: 'Seiten' })
    const top = within(tree)
      .getAllByRole('treeitem')
      .filter((item) => item.getAttribute('aria-level') === '1')
    expect(top.map((item) => item.getAttribute('data-page-id'))).toEqual([start.id, folder.id])
    const agents = within(tree).getByRole('treeitem', { name: /Agenten/ })
    expect(within(agents).getAllByRole('img', { name: 'Von Agenten geführt' })).toHaveLength(3)
    const plain = within(tree).getByRole('treeitem', { name: 'Start' })
    expect(within(plain).queryByRole('img', { name: 'Von Agenten geführt' })).toBeNull()
  })

  test('a memory page says an agent keeps it and people may correct it; the AI mark and run', async () => {
    memoryApi()
    await renderApp(`/spaces/${space.id}/p/_agenten/hilda/gedaechtnis`)
    const article = await screen.findByRole('article')
    expect(
      await within(article).findByText(/Ein Agent führt diese Seite als sein Gedächtnis/),
    ).toBeInTheDocument()
    expect(within(article).getByText(/Du kannst sie korrigieren/)).toBeInTheDocument()
    expect(within(article).getByText('Von einer KI geschrieben')).toBeInTheDocument()
    expect(await within(article).findByRole('link', { name: 'Lauf ansehen' })).toHaveAttribute(
      'href',
      '/runs/run-9',
    )
  })

  test('without AI the page reads as it is, without a run link', async () => {
    const api = memoryApi(false)
    await renderApp(`/spaces/${space.id}/p/_agenten/hilda/gedaechtnis`)
    const article = await screen.findByRole('article')
    expect(within(article).getByText('Von einer KI geschrieben')).toBeInTheDocument()
    expect(within(article).queryByRole('link', { name: 'Lauf ansehen' })).toBeNull()
    expect(api.find('GET', '/api/runs/run-9')).toHaveLength(0)
  })

  test('a page a person wrote shows neither the note nor the mark', async () => {
    const api = memoryApi()
    await renderApp(`/spaces/${space.id}/p/start`)
    const article = await screen.findByRole('article')
    expect(await within(article).findByRole('heading', { name: 'Start' })).toBeInTheDocument()
    expect(within(article).queryByText(/als sein Gedächtnis/)).toBeNull()
    expect(within(article).queryByText('Von einer KI geschrieben')).toBeNull()
    expect(api.find('GET', `/api/pages/${start.id}/versions`)).toHaveLength(0)
  })

  test("the history links an agent's versions to their runs", async () => {
    memoryApi()
    await renderApp(`/spaces/${space.id}/p/_agenten/hilda/gedaechtnis?view=versions`)
    const table = await screen.findByRole('table')
    await waitFor(() =>
      expect(
        within(table)
          .getAllByRole('link', { name: 'Lauf ansehen' })
          .map((link) => link.getAttribute('href')),
      ).toEqual(['/runs/run-9', '/runs/run-8']),
    )
  })
})
