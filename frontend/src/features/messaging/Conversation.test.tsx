import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, test } from 'vitest'
import type { Conversation, Message, SpaceRole } from '@/lib/api'
import { apiError, type Call, makeEntry, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { makeConversation, makeMessage, shellRoutes, written } from '@/test/messaging'
import { renderApp } from '@/test/render'
import { clearPending } from './conversation/pending'

const me = makeMe(['directory.read'])
const mine = { type: 'user' as const, id: me.user.id, name: me.user.name }

afterEach(() => clearPending())

function conversationApi({
  conversation,
  messages,
  role = 'viewer',
  extra = {},
}: {
  conversation: Conversation
  messages: Message[]
  role?: SpaceRole
  extra?: Record<string, unknown>
}) {
  const space = makeSpace({ id: 'space-1', name: 'Handbuch', my_role: role })
  return mockApi({
    ...shellRoutes(me, [space]),
    'GET /api/spaces/:id': space,
    'GET /api/conversations/:id': conversation,
    'GET /api/conversations/:id/messages': page(messages),
    'POST /api/conversations/:id/read': { status: 204 },
    ...(extra as Record<string, object>),
  })
}

function article(author: string, text: string): HTMLElement {
  return screen
    .getAllByRole('article', { name: `Nachricht von ${author}` })
    .find((a) => a.textContent?.includes(text))!
}

describe('conversation', () => {
  test('actions follow authorship, can_post and my_role only', async () => {
    const channel = makeConversation()
    const messages = [
      makeMessage({ conversation_id: channel.id, body_md: 'Von Lea' }),
      makeMessage({ conversation_id: channel.id, body_md: 'Von mir', author: mine }),
    ]
    conversationApi({ conversation: channel, messages, role: 'viewer' })
    await renderApp(`/c/${channel.id}`)
    await screen.findByText('Von Lea')
    const own = within(article('Mia Muster', 'Von mir'))
    expect(own.getByRole('button', { name: 'Nachricht bearbeiten' })).toBeInTheDocument()
    expect(own.getByRole('button', { name: 'Nachricht löschen' })).toBeInTheDocument()
    const other = within(article('Lea Löwe', 'Von Lea'))
    expect(other.queryByRole('button', { name: 'Nachricht bearbeiten' })).toBeNull()
    expect(other.queryByRole('button', { name: 'Nachricht löschen' })).toBeNull()
    expect(other.getByRole('button', { name: 'Reaktion hinzufügen' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Nachricht an #allgemein' })).toBeInTheDocument()
  })

  test('a moderator of the space deletes others’ messages, never edits them', async () => {
    const channel = makeConversation()
    const messages = [makeMessage({ conversation_id: channel.id, body_md: 'Von Lea' })]
    conversationApi({ conversation: channel, messages, role: 'moderator' })
    await renderApp(`/c/${channel.id}`)
    await screen.findByText('Von Lea')
    const other = within(article('Lea Löwe', 'Von Lea'))
    expect(other.getByRole('button', { name: 'Nachricht löschen' })).toBeInTheDocument()
    expect(other.queryByRole('button', { name: 'Nachricht bearbeiten' })).toBeNull()
  })

  test('where one may not post there is no composer and no editing, only the reason', async () => {
    const channel = makeConversation({ can_post: false, archived_at: '2026-11-13T10:00:00Z' })
    const messages = [makeMessage({ conversation_id: channel.id, body_md: 'Alt', author: mine })]
    conversationApi({ conversation: channel, messages, role: 'admin' })
    await renderApp(`/c/${channel.id}`)
    await screen.findByText('Alt')
    expect(screen.queryByRole('combobox', { name: /Nachricht an/ })).toBeNull()
    expect(screen.getByRole('note')).toHaveTextContent('Dieser Kanal ist archiviert.')
    const own = within(article('Mia Muster', 'Alt'))
    expect(own.queryByRole('button', { name: 'Nachricht bearbeiten' })).toBeNull()
    expect(own.queryByRole('button', { name: 'Nachricht löschen' })).toBeNull()
  })

  test('sending is optimistic; a failure offers to send again with the same key', async () => {
    const channel = makeConversation()
    let release: (reply: unknown) => void = () => {}
    let attempts = 0
    const stored: Message[] = []
    const api = conversationApi({
      conversation: channel,
      messages: [],
      extra: {
        'GET /api/conversations/:id/messages': () => page(stored),
        'POST /api/conversations/:id/messages': (call: Call) => {
          attempts += 1
          if (attempts === 1) return new Promise((resolve) => (release = resolve))
          const body = call.body as { body_md: string; client_id: string }
          const message = makeMessage({
            conversation_id: channel.id,
            author: mine,
            body_md: body.body_md,
            client_id: body.client_id,
          })
          stored.unshift(message)
          return { status: 201, body: written(message) }
        },
      },
    })
    const { user } = await renderApp(`/c/${channel.id}`)
    const box = await screen.findByRole('combobox', { name: 'Nachricht an #allgemein' })
    await user.type(box, 'Erste Zeile{Shift>}{Enter}{/Shift}zweite Zeile{Enter}')
    expect(box).toHaveValue('')
    const pending = await screen.findByText('Wird gesendet …')
    expect(pending.closest('article')).toHaveTextContent('Erste Zeile')
    release(apiError(503, 'server.busy'))
    expect(await screen.findByText(/Nicht gesendet/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Erneut senden' }))
    await waitFor(() => expect(screen.queryByText(/Nicht gesendet/)).toBeNull())
    expect(screen.queryByText('Wird gesendet …')).toBeNull()
    expect(await screen.findByText(/zweite Zeile/)).toBeInTheDocument()
    const posts = api.find('POST', `/api/conversations/${channel.id}/messages`)
    expect(posts).toHaveLength(2)
    const [first, second] = posts.map((c) => c.body as { body_md: string; client_id: string })
    expect(first!.body_md).toBe('Erste Zeile\nzweite Zeile')
    expect(second).toEqual(first)
  })

  test('the mention picker inserts the structured mention and sends its id', async () => {
    const channel = makeConversation()
    const lea = makeEntry({ name: 'Lea Löwe' })
    const api = conversationApi({
      conversation: channel,
      messages: [],
      extra: {
        'GET /api/directory': (call: Call) =>
          page(
            call.query.get('type') === 'user' && 'lea löwe'.includes(call.query.get('q') ?? '')
              ? [lea]
              : [],
          ),
        'POST /api/conversations/:id/messages': (call: Call) => {
          const body = call.body as { body_md: string; client_id: string }
          const stored = makeMessage({ conversation_id: channel.id, author: mine, ...body })
          return { status: 201, body: written(stored, [lea.id]) }
        },
      },
    })
    const { user } = await renderApp(`/c/${channel.id}`)
    const box = await screen.findByRole('combobox', { name: 'Nachricht an #allgemein' })
    expect(box).toHaveAttribute('aria-expanded', 'false')
    await user.type(box, 'Frage an @le')
    const option = await screen.findByRole('option', { name: 'Lea Löwe' })
    expect(option).toHaveAttribute('aria-selected', 'true')
    expect(box).toHaveAttribute('aria-expanded', 'true')
    expect(box).toHaveAttribute('aria-autocomplete', 'list')
    await user.keyboard('{Enter}')
    expect(box).toHaveAttribute('aria-expanded', 'false')
    expect(box).toHaveValue(`Frage an @[Lea Löwe](user:${lea.id}) `)
    await user.type(box, 'bitte{Enter}')
    await waitFor(() =>
      expect(api.find('POST', `/api/conversations/${channel.id}/messages`)).toHaveLength(1),
    )
    const sent = api.find('POST', `/api/conversations/${channel.id}/messages`)[0]!.body as {
      body_md: string
      mentions: string[]
    }
    expect(sent.mentions).toEqual([lea.id])
    expect(sent.body_md).toBe(`Frage an @[Lea Löwe](user:${lea.id}) bitte`)
    expect(
      await screen.findByText('Nicht benachrichtigt: Lea Löwe – kann dieses Gespräch nicht sehen.'),
    ).toBeInTheDocument()
  })

  test("the mention picker offers only people who can see the channel's space", async () => {
    const channel = makeConversation()
    const api = conversationApi({
      conversation: channel,
      messages: [],
      extra: { 'GET /api/directory': page([makeEntry({ name: 'Lea Löwe' })]) },
    })
    const { user } = await renderApp(`/c/${channel.id}`)
    await user.type(await screen.findByRole('combobox', { name: 'Nachricht an #allgemein' }), '@le')
    await screen.findByRole('option', { name: 'Lea Löwe' })
    expect(api.find('GET', '/api/directory').at(-1)!.query.get('space_id')).toBe('space-1')
  })

  test('in a direct message the mention picker offers its other participants only', async () => {
    const dm = makeConversation({
      kind: 'dm',
      space_id: null,
      name: null,
      participants: [
        { id: me.user.id, name: me.user.name, is_active: true },
        { id: 'jan', name: 'Jan Jansen', is_active: true },
        { id: 'jo', name: 'Jo Gone', is_active: false },
      ],
    })
    const api = conversationApi({ conversation: dm, messages: [] })
    const { user } = await renderApp(`/c/${dm.id}`)
    await user.type(await screen.findByRole('combobox', { name: /Nachricht an/ }), '@j')
    expect(await screen.findByRole('option', { name: 'Jan Jansen' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Jo Gone' })).toBeNull()
    expect(screen.queryByRole('option', { name: me.user.name })).toBeNull()
    expect(api.find('GET', '/api/directory')).toHaveLength(0)
  })

  test('a thread whose message is not among the loaded ones shows it all the same', async () => {
    const channel = makeConversation()
    const parent = makeMessage({
      conversation_id: channel.id,
      body_md: 'Alte Frage',
      reply_count: 1,
    })
    const reply = makeMessage({
      conversation_id: channel.id,
      parent_id: parent.id,
      body_md: 'Späte Antwort',
    })
    const api = conversationApi({
      conversation: channel,
      messages: [makeMessage({ conversation_id: channel.id, body_md: 'Neueres' })],
      extra: {
        'GET /api/messages/:id': parent,
        'GET /api/messages/:id/replies': page([reply]),
      },
    })
    await renderApp(`/c/${channel.id}?thread=${parent.id}&message=${reply.id}`)
    const thread = await screen.findByRole('complementary', { name: 'Thread' })
    expect(await within(thread).findByText('Alte Frage')).toBeInTheDocument()
    expect(within(thread).getByText('Späte Antwort')).toBeInTheDocument()
    expect(api.find('GET', `/api/messages/${parent.id}`)).toHaveLength(1)
  })

  test('a conversation one lost access to says so instead of failing', async () => {
    const channel = makeConversation()
    const api = mockApi({
      ...shellRoutes(me),
      'GET /api/conversations/:id': apiError(404, 'conversation.not_found'),
    })
    await renderApp(`/c/${channel.id}`)
    expect(
      await screen.findByText(
        'Dieses Gespräch gibt es nicht (mehr), oder du hast keinen Zugang mehr.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Zur Aktivität' })).toBeInTheDocument()
    // The sidebar forgets it too, and a 404 is not asked again.
    await waitFor(() => expect(api.find('GET', '/api/channels').length).toBeGreaterThan(1))
    expect(api.find('GET', `/api/conversations/${channel.id}`)).toHaveLength(1)
  })

  test('the "new" marker stands before the first unread message and the newest is read', async () => {
    const channel = makeConversation()
    const messages = [
      makeMessage({
        conversation_id: channel.id,
        body_md: 'Drei',
        created_at: '2026-11-13T09:03:00Z',
      }),
      makeMessage({
        conversation_id: channel.id,
        body_md: 'Zwei',
        created_at: '2026-11-13T09:02:00Z',
      }),
      makeMessage({
        conversation_id: channel.id,
        body_md: 'Eins',
        created_at: '2026-11-13T09:01:00Z',
      }),
    ]
    const api = conversationApi({
      conversation: channel,
      messages,
      extra: {
        'GET /api/conversations/unread': page([
          { conversation_id: channel.id, unread: 2, mentions: 0 },
        ]),
      },
    })
    await renderApp(`/c/${channel.id}`)
    await screen.findByText('Drei')
    const items = screen.getAllByRole('listitem').map((li) => li.textContent ?? '')
    const marker = items.findIndex((text) => text === 'Neu')
    expect(items[marker + 1]).toContain('Zwei')
    expect(items[marker - 1]).toContain('Eins')
    await waitFor(() =>
      expect(api.find('POST', `/api/conversations/${channel.id}/read`)[0]?.body).toEqual({
        message_id: messages[0]!.id,
      }),
    )
  })
})
