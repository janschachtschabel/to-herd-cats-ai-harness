import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, test } from 'vitest'
import { type Call, makeMe, makePage, makeSpace, mockApi, nodeOf, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { clearPending } from '../conversation/pending'

afterEach(() => clearPending())

const space = makeSpace({ id: 'space-1', name: 'Handbuch', my_role: 'viewer' })
const urlaub = makePage({ space_id: space.id, title: 'Urlaub', path: 'urlaub' })
const thread = makeConversation({ kind: 'thread_page', page_id: urlaub.id, name: null })

function discussionApi() {
  const published = makeMessage({
    conversation_id: thread.id,
    kind: 'system',
    author: null,
    body_md: '{"key": "page.published", "actor": "jan"}',
    system: { key: 'page.published', actor: { id: 'jan', name: 'Jan Jansen' }, number: null },
    created_at: '2026-11-13T09:00:00Z',
  })
  const restored = makeMessage({
    conversation_id: thread.id,
    kind: 'system',
    author: null,
    body_md: '{"key": "page.version_restored", "actor": "x", "number": 2}',
    system: { key: 'page.version_restored', actor: null, number: 2 },
    created_at: '2026-11-13T09:01:00Z',
  })
  const comment = makeMessage({
    conversation_id: thread.id,
    body_md: 'Gilt das auch für Teilzeit?',
    created_at: '2026-11-13T09:02:00Z',
  })
  return mockApi({
    ...shellRoutes(makeMe([]), [space]),
    'GET /api/spaces/:id': space,
    'GET /api/spaces/:id/pages/tree': page([nodeOf(urlaub)]),
    'GET /api/spaces/:id/pages/by-path': urlaub,
    'GET /api/tags': page([]),
    'GET /api/pages/:id/attachments': page([]),
    'GET /api/pages/:id': urlaub,
    'GET /api/pages/:id/thread': thread,
    'GET /api/conversations/:id/messages': (call: Call) =>
      page(
        call.query.get('include_system') === 'false' ? [comment] : [comment, restored, published],
      ),
    'POST /api/conversations/:id/read': { status: 204 },
  })
}

describe('page discussion', () => {
  test('the timeline is worded from key and parameters and can be hidden', async () => {
    const api = discussionApi()
    const { user } = await renderApp(`/spaces/${space.id}/p/urlaub`)
    await user.click(await screen.findByRole('button', { name: 'Diskussion' }))
    const panel = await screen.findByRole('complementary', { name: 'Diskussion' })
    expect(
      await within(panel).findByText('Jan Jansen hat die Seite veröffentlicht.'),
    ).toBeInTheDocument()
    expect(within(panel).getByText('Jemand hat Version 2 wiederhergestellt.')).toBeInTheDocument()
    expect(within(panel).getByText('Gilt das auch für Teilzeit?')).toBeInTheDocument()
    expect(within(panel).getByRole('textbox', { name: 'Zur Seite schreiben' })).toBeInTheDocument()

    await user.click(within(panel).getByRole('checkbox', { name: 'Systemmeldungen ausblenden' }))
    await waitFor(() =>
      expect(within(panel).queryByText('Jan Jansen hat die Seite veröffentlicht.')).toBeNull(),
    )
    expect(within(panel).getByText('Gilt das auch für Teilzeit?')).toBeInTheDocument()
    const asked = api.find('GET', `/api/conversations/${thread.id}/messages`)
    expect(asked.at(-1)!.query.get('include_system')).toBe('false')
  })

  test('a link to a page discussion by page id opens the page with the discussion', async () => {
    discussionApi()
    const { router } = await renderApp(`/go/page/${urlaub.id}`)
    await waitFor(() => expect(router.state.location.pathname).toBe(`/spaces/${space.id}/p/urlaub`))
    expect(await screen.findByRole('complementary', { name: 'Diskussion' })).toBeInTheDocument()
  })
})
