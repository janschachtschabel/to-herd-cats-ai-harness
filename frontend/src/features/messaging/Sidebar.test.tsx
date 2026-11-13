import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { type Call, makeEntry, makeMe, makeSpace, mockApi, page } from '@/test/api'
import { makeConversation, shellRoutes } from '@/test/messaging'
import { renderApp } from '@/test/render'

function section(id: string): HTMLElement {
  const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' })
  return nav.querySelector(`[data-section="${id}"]`) as HTMLElement
}

describe('sidebar messaging', () => {
  test('channels and direct messages with unread counts; mentions stand out', async () => {
    const me = makeMe(['directory.read'])
    const general = makeConversation({ name: 'allgemein' })
    const team = makeConversation({ name: 'team-dienste' })
    const dm = makeConversation({
      kind: 'dm',
      space_id: null,
      name: null,
      participants: [
        { id: me.user.id, name: 'Mia Muster', is_active: true },
        { id: 'jan', name: 'Jan Jansen', is_active: true },
        { id: 'lea', name: 'Lea Löwe', is_active: true },
      ],
    })
    mockApi({
      ...shellRoutes(me),
      'GET /api/channels': page([general, team]),
      'GET /api/dms': page([{ ...dm, last_message_at: null }]),
      'GET /api/conversations/unread': page([
        { conversation_id: general.id, unread: 3, mentions: 0 },
        { conversation_id: dm.id, unread: 1, mentions: 1 },
      ]),
      'GET /api/activity/count': { open: 4, unread: 2 },
    })
    await renderApp('/spaces')
    const channels = within(section('channels'))
    const link = await channels.findByRole('link', { name: /allgemein/ })
    expect(link).toHaveTextContent('3 ungelesene Nachrichten')
    expect(channels.getByRole('link', { name: /team-dienste/ })).not.toHaveTextContent(/ungelesen/)
    const direct = within(section('direct'))
    expect(await direct.findByRole('link', { name: /Jan Jansen, Lea Löwe/ })).toHaveTextContent(
      '1 Erwähnung von dir',
    )
    const activity = within(section('activity'))
    expect(await activity.findByRole('link', { name: /Aktivität/ })).toHaveTextContent(
      '2 ungelesene Einträge',
    )
    await waitFor(() => expect(document.title).toBe('(2) Herd'))
  })

  test('"create channel" only with a space one moderates; "direct message" only with the directory', async () => {
    const viewer = makeSpace({ name: 'Lesen', my_role: 'viewer' })
    const moderator = makeSpace({ name: 'Moderieren', my_role: 'moderator' })
    mockApi(shellRoutes(makeMe([]), [viewer]))
    await renderApp('/spaces')
    await within(section('spaces')).findByRole('link', { name: 'Lesen' })
    expect(screen.queryByRole('button', { name: 'Kanal anlegen' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Direktnachricht beginnen' })).toBeNull()

    document.body.innerHTML = ''
    mockApi(shellRoutes(makeMe(['directory.read']), [viewer, moderator]))
    await renderApp('/spaces')
    expect(await screen.findByRole('button', { name: 'Kanal anlegen' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Direktnachricht beginnen' })).toBeInTheDocument()
  })

  test('creating a channel offers only the spaces one moderates and opens it', async () => {
    const viewer = makeSpace({ name: 'Lesen', my_role: 'viewer' })
    const moderator = makeSpace({ name: 'Moderieren', my_role: 'moderator' })
    const created = makeConversation({ name: 'neu', space_id: moderator.id })
    const api = mockApi({
      ...shellRoutes(makeMe([]), [viewer, moderator]),
      'POST /api/spaces/:id/channels': { status: 201, body: created },
      'GET /api/conversations/:id': created,
      'GET /api/conversations/:id/messages': page([]),
      'GET /api/spaces/:id': moderator,
    })
    const { user, router } = await renderApp('/spaces')
    await user.click(await screen.findByRole('button', { name: 'Kanal anlegen' }))
    const dialog = await screen.findByRole('dialog')
    const select = within(dialog).getByLabelText('Bereich')
    expect(
      within(select)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Moderieren'])
    await user.type(within(dialog).getByLabelText('Name'), 'neu')
    await user.click(within(dialog).getByRole('button', { name: 'Anlegen' }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/c/${created.id}`))
    expect(api.find('POST', `/api/spaces/${moderator.id}/channels`)[0]!.body).toEqual({
      name: 'neu',
      topic: null,
    })
  })

  test('a direct message with chosen people opens; a guest is told why not', async () => {
    const lea = makeEntry({ name: 'Lea Löwe' })
    const api = mockApi({
      ...shellRoutes(makeMe(['directory.read'])),
      'GET /api/directory': (call: Call) =>
        call.query.get('type') === 'user' ? page([lea]) : page([]),
      'POST /api/dms': {
        status: 403,
        body: { error: { code: 'dm.guest_cannot_open', message: 'x', trace_id: '0' } },
      },
    })
    const { user } = await renderApp('/spaces')
    await user.click(await screen.findByRole('button', { name: 'Direktnachricht beginnen' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('combobox', { name: 'Personen' }))
    await user.click(await within(dialog).findByRole('option', { name: /Lea Löwe/ }))
    expect(within(dialog).getByRole('list', { name: 'Ausgewählte Personen' })).toHaveTextContent(
      'Lea Löwe',
    )
    await user.click(within(dialog).getByRole('button', { name: 'Öffnen' }))
    expect(
      await within(dialog).findByText('Gäste können keine Direktnachrichten beginnen.'),
    ).toBeInTheDocument()
    expect(api.find('POST', '/api/dms')[0]!.body).toEqual({ user_ids: [lea.id] })
  })
})
