import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import type { MessageHit, SearchHit, TicketHit } from '@/lib/api'
import { makeMe, makePage, makeSpace, mockApi, nodeOf, page } from '@/test/api'
import { renderApp } from '@/test/render'

const space = makeSpace({ name: 'Handbuch', my_role: 'viewer' })
const urlaub = makePage({ space_id: space.id, title: 'Urlaub', path: 'urlaub' })

function hit(overrides: Partial<SearchHit> = {}): SearchHit {
  return {
    type: 'page',
    id: urlaub.id,
    space_id: space.id,
    space_name: space.name,
    title: 'Urlaub',
    path: 'urlaub',
    snippet: 'Der ⟦Urlaub⟧ <b>beginnt</b> <script>x()</script>',
    score: 1,
    ...overrides,
  }
}

function searchApi() {
  return mockApi({
    'GET /api/auth/me': makeMe([]),
    'GET /api/spaces': page([space]),
    'GET /api/spaces/:id': space,
    'GET /api/spaces/:id/pages/tree': page([nodeOf(urlaub)]),
    'GET /api/spaces/:id/pages/by-path': urlaub,
    'GET /api/tags': page([]),
    'GET /api/pages/:id/attachments': page([]),
    'GET /api/search': (call) =>
      page(call.query.get('q') === 'urlaub' ? [hit(), hit({ id: 'x', title: 'Zweiter' })] : []),
  })
}

describe('search', () => {
  test('search highlights markers and escapes html', async () => {
    searchApi()
    const { user } = await renderApp('/spaces')
    await user.click(screen.getByRole('button', { name: /Suche/ }))
    await user.type(await screen.findByRole('combobox', { name: 'Suchbegriff' }), 'urlaub')
    const list = await screen.findByRole('listbox', { name: 'Treffer' })
    const first = within(list).getAllByRole('option')[0]!
    expect(within(first).getByText('Urlaub', { selector: 'mark' })).toBeInTheDocument()
    expect(first.querySelector('b, script')).toBeNull()
    expect(first).toHaveTextContent('<b>beginnt</b> <script>x()</script>')
  })

  test('Ctrl+K opens the palette; arrows choose and Enter opens the page', async () => {
    const api = searchApi()
    const { router, user } = await renderApp(`/spaces/${space.id}`)
    await screen.findByRole('tree')
    await user.keyboard('{Control>}k{/Control}')
    const input = await screen.findByRole('combobox', { name: 'Suchbegriff' })
    await user.click(screen.getByRole('checkbox', { name: 'Nur in diesem Bereich' }))
    await user.type(input, 'urlaub')
    await screen.findAllByRole('option')
    await waitFor(() =>
      expect(api.find('GET', '/api/search').at(-1)?.query.get('space_id')).toBe(space.id),
    )
    await user.keyboard('{ArrowDown}{ArrowUp}')
    expect(input).toHaveAttribute('aria-activedescendant', screen.getAllByRole('option')[0]!.id)
    await user.keyboard('{Enter}')
    await waitFor(() => expect(router.state.location.pathname).toBe(`/spaces/${space.id}/p/urlaub`))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  test('no results and an empty term say so; nothing is asked for blank input', async () => {
    const api = searchApi()
    const { user } = await renderApp('/spaces')
    await user.keyboard('{Control>}k{/Control}')
    expect(
      await screen.findByText(
        'Gib einen Begriff ein, um Seiten, Nachrichten und Tickets zu finden.',
      ),
    ).toBeInTheDocument()
    await user.type(screen.getByRole('combobox', { name: 'Suchbegriff' }), 'nix')
    expect(await screen.findByText('Keine Treffer.')).toBeInTheDocument()
    expect(api.find('GET', '/api/search').map((c) => c.query.get('q'))).toEqual(['nix'])
  })

  test('message hits show where and who, and open the conversation at the message', async () => {
    const message: MessageHit = {
      type: 'message',
      id: '00000000-0000-7000-b000-000000000001',
      parent_id: '00000000-0000-7000-b000-000000000002',
      conversation: {
        id: 'chan-1',
        kind: 'channel',
        name: 'allgemein',
        space_id: space.id,
        page_id: null,
        ticket_number: null,
      },
      author: { type: 'user', id: 'jan', name: 'Jan Jansen' },
      created_at: '2026-11-13T09:00:00Z',
      snippet: 'Wann ist ⟦Urlaub⟧?',
      score: 2,
    }
    mockApi({
      'GET /api/auth/me': makeMe([]),
      'GET /api/spaces': page([space]),
      'GET /api/search': (call) => {
        expect(call.query.get('types')).toBe('page,message,ticket')
        return page([message, hit()])
      },
      'GET /api/conversations/:id': {
        status: 404,
        body: { error: { code: 'conversation.not_found' } },
      },
    })
    const { router, user } = await renderApp('/spaces')
    await user.keyboard('{Control>}k{/Control}')
    await user.type(await screen.findByRole('combobox', { name: 'Suchbegriff' }), 'urlaub')
    const first = (await screen.findAllByRole('option'))[0]!
    expect(first).toHaveTextContent('allgemeinvon Jan Jansen')
    expect(within(first).getByText('Urlaub', { selector: 'mark' })).toBeInTheDocument()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(router.state.location.pathname).toBe('/c/chan-1'))
    expect(router.state.location.search).toEqual({
      thread: message.parent_id,
      message: message.id,
    })
  })
})

describe('ticket hits', () => {
  test('a key finds its ticket first; Enter opens the ticket', async () => {
    const ticket: TicketHit = {
      type: 'ticket',
      id: '00000000-0000-7000-b000-000000000042',
      number: 42,
      key: 'HC-42',
      title: 'Login schlägt fehl',
      kind: 'bug',
      status: { id: 's1', name: 'In Arbeit', category: 'active' },
      space_id: space.id,
      space_name: space.name,
      snippet: '',
      score: 101,
    }
    mockApi({
      'GET /api/auth/me': makeMe([]),
      'GET /api/spaces': page([space]),
      'GET /api/search': page([ticket, hit()]),
      'GET /api/tickets/:number': { status: 404, body: { error: { code: 'ticket.not_found' } } },
    })
    const { router, user } = await renderApp('/spaces')
    await user.keyboard('{Control>}k{/Control}')
    await user.type(await screen.findByRole('combobox', { name: 'Suchbegriff' }), 'HC-42')
    const first = (await screen.findAllByRole('option'))[0]!
    expect(first).toHaveTextContent('HC-42')
    expect(first).toHaveTextContent('Login schlägt fehl')
    expect(first).toHaveTextContent('In Arbeit')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(router.state.location.pathname).toBe('/tickets/42'))
  })
})
