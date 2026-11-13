import { act, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import * as Y from 'yjs'
import { makeMe, makePage, mockApi, nodeOf, page } from '@/test/api'
import { renderApp } from '@/test/render'
import { fake, join, liveApi, space, typeInto } from './fakeLive.test-helper'

const { connections, events } = fake

vi.mock('./connect', async (original) => ({
  ...(await original<typeof import('./connect')>()),
  connectLive: (await import('./fakeLive.test-helper')).fakeConnectLive,
}))

beforeEach(() => fake.reset())

describe('live editor', () => {
  test('shows presence of other editors and the sync state', async () => {
    const current = makePage({ space_id: space.id })
    liveApi('editor', () => current)
    await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    expect(connections[0]).toMatchObject({ pageId: current.id, generation: 0 })
    expect(screen.getByRole('status')).toHaveTextContent('Verbindet …')
    join(connections[0]!)
    act(() =>
      connections[0]!.handlers.onPeers([
        { clientId: 1, user: { name: 'Mia Muster', color: '#1d4ed8' } },
        { clientId: 2, user: { name: 'Lea Löwe', color: '#be185d' } },
      ]),
    )
    const present = screen.getByRole('list', { name: 'Ebenfalls in der Seite' })
    expect(present).toHaveTextContent('Lea Löwe')
    expect(present).not.toHaveTextContent('Mia Muster')
    expect(screen.getByRole('status')).toHaveTextContent('Synchronisiert')
    act(() => connections[0]!.handlers.onUnsynced(2))
    expect(screen.getByRole('status')).toHaveTextContent('Speichert …')
    expect(await screen.findByRole('textbox', { name: 'Inhalt von „Handbuch“' })).toHaveAttribute(
      'contenteditable',
      'true',
    )
  })

  test('4409 ends the connection, refetches and joins the new generation', async () => {
    let current = makePage({ space_id: space.id, content_md: 'alt' })
    const api = liveApi('editor', () => current)
    await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    const first = connections[0]!
    join(first)
    typeInto(first.doc, 'ungespeichert')
    current = { ...current, content_md: 'neu', collab_generation: 1, version: 2 }
    act(() => first.handlers.onClose(4409))
    await waitFor(() => expect(connections).toHaveLength(2))
    expect(first.destroyed).toBe(true)
    expect(api.find('GET', `/api/pages/${current.id}`)).toHaveLength(1)
    expect(connections[1]!.generation).toBe(1)
    expect(connections[1]!.doc).not.toBe(first.doc)
    expect(screen.getByText(/außerhalb der Live-Sitzung geändert/)).toBeInTheDocument()
    // What was typed in the ended generation can still be copied.
    expect(
      screen.getByRole('button', { name: 'Meinen Text als Markdown kopieren' }),
    ).toBeInTheDocument()
  })

  test.each([
    [4403, 'Dir fehlt das Schreibrecht'],
    [4401, 'Deine Sitzung ist abgelaufen'],
    [4404, 'nicht mehr sichtbar'],
    [4413, 'zu groß für die Live-Bearbeitung'],
  ])('%i stops reconnecting and leaves the text read-only', async (code, message) => {
    const current = makePage({ space_id: space.id, content_md: 'alt' })
    liveApi('editor', () => current)
    await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    join(connections[0]!)
    typeInto(connections[0]!.doc, 'mein Text')
    const editor = await screen.findByRole('textbox', { name: 'Inhalt von „Handbuch“' })
    await waitFor(() => expect(editor).toHaveTextContent('mein Text'))
    act(() => connections[0]!.handlers.onClose(code))
    expect(await screen.findByText(new RegExp(message))).toBeInTheDocument()
    await waitFor(() => expect(editor).toHaveAttribute('contenteditable', 'false'))
    expect(connections[0]!.destroyed).toBe(true)
    expect(editor).toHaveTextContent('mein Text')
    expect(
      screen.getByRole('button', { name: 'Meinen Text als Markdown kopieren' }),
    ).toBeInTheDocument()
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(connections).toHaveLength(1)
    // Too large for live editing (review R8): the Markdown editor is offered.
    const offered = screen.queryByRole('link', { name: 'Im Markdown-Editor bearbeiten' })
    expect(offered !== null).toBe(code === 4413)
  })

  test('4422: a page the live editor would change is offered in the Markdown editor', async () => {
    const current = makePage({ space_id: space.id, content_md: '- a\n\n* b' })
    liveApi('editor', () => current)
    const { router, user } = await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    // The editor's own empty paragraph never reaches the server (found in a browser,
    // review R18): leaving must not ask about unsaved changes nobody made.
    act(() => connections[0]!.handlers.onUnsynced(1))
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    act(() => connections[0]!.handlers.onClose(4422))
    expect(
      await screen.findByText(/die der Live-Editor nicht unverändert bearbeiten kann/),
    ).toBeInTheDocument()
    expect(connections[0]!.destroyed).toBe(true)
    expect(screen.queryByRole('button', { name: 'Neu laden' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Im Markdown-Editor bearbeiten' }))
    await waitFor(() => expect(router.state.location.search).toEqual({ view: 'edit' }))
    expect(confirm).not.toHaveBeenCalled()
    confirm.mockRestore()
  })

  test('1013 and other transient closes leave reconnecting to the provider', async () => {
    const current = makePage({ space_id: space.id })
    liveApi('editor', () => current)
    await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    join(connections[0]!)
    act(() => {
      connections[0]!.handlers.onClose(1013)
      connections[0]!.handlers.onConnected(false)
    })
    expect(screen.getByRole('status')).toHaveTextContent('Getrennt – neuer Versuch …')
    expect(connections[0]!.destroyed).toBe(false)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  test('logging out first sends what is typed in the live editor (review R2)', async () => {
    const current = makePage({ space_id: space.id })
    liveApi('editor', () => current)
    mockApi({
      'GET /api/auth/me': makeMe([]),
      'GET /api/spaces': page([{ ...space, my_role: 'editor' }]),
      'GET /api/spaces/:id': { ...space, my_role: 'editor' },
      'GET /api/spaces/:id/pages/tree': () => page([nodeOf(current)]),
      'GET /api/spaces/:id/pages/by-path': () => current,
      'GET /api/pages/:id': () => current,
      'GET /api/tags': page([]),
      'GET /api/pages/:id/attachments': page([]),
      'POST /api/auth/logout': () => {
        events.push('logout')
        return { status: 204 }
      },
    })
    const { user } = await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    join(connections[0]!)
    typeInto(connections[0]!.doc, 'letzter Satz')
    await user.click(screen.getByRole('button', { name: /^Menü von/ }))
    await user.click(await screen.findByRole('menuitem', { name: 'Abmelden' }))
    await waitFor(() => expect(events).toEqual(['flushed', 'logout']))
    expect(connections[0]!.destroyed).toBe(true)
  })

  test('"Fertig" waits for the save, then shows what the server stored (review R3)', async () => {
    let current = makePage({ space_id: space.id, content_md: 'Alter Text' })
    const api = liveApi('editor', () => current)
    fake.finishAnswer = () => {
      current = { ...current, content_md: 'Alter Text NEU-GETIPPT', version: 2 }
      return true
    }
    const { router, user } = await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    join(connections[0]!)
    typeInto(connections[0]!.doc, 'NEU-GETIPPT')
    const trees = api.find('GET', `/api/spaces/${space.id}/pages/tree`).length
    await user.click(screen.getByRole('button', { name: 'Fertig' }))
    await waitFor(() => expect(router.state.location.search).toEqual({}))
    expect(await screen.findByText('Alter Text NEU-GETIPPT')).toBeInTheDocument()
    expect(events).toEqual(['flushed'])
    expect(connections[0]!.destroyed).toBe(true)
    expect(api.find('GET', `/api/spaces/${space.id}/pages/tree`).length).toBeGreaterThan(trees)
  })

  test('"Fertig" stays in the editor while the server has not stored everything', async () => {
    const current = makePage({ space_id: space.id, content_md: 'Alter Text' })
    liveApi('editor', () => current)
    fake.finishAnswer = () => false
    const { router, user } = await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    join(connections[0]!)
    await user.click(screen.getByRole('button', { name: 'Fertig' }))
    expect(await screen.findByText(/noch nicht gespeichert/)).toBeInTheDocument()
    expect(router.state.location.search).toEqual({ view: 'live' })
    expect(connections[0]!.destroyed).toBe(false)
  })

  test('a state that cannot be saved as Markdown is shown, and the session goes on', async () => {
    const current = makePage({ space_id: space.id, content_md: 'Alter Text' })
    liveApi('editor', () => current)
    const { router } = await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    join(connections[0]!)
    typeInto(connections[0]!.doc, 'Erster Absatz')
    typeInto(connections[0]!.doc, 'Zweiter Absatz')
    act(() => connections[0]!.handlers.onUnrepresentable({ kind: 'markdown', block: 1 }))
    expect(screen.getByText(/lässt sich so nicht als Markdown speichern/)).toBeInTheDocument()
    // The notice names the cause and the block (fix wave 3).
    expect(screen.getByText(/würde als Markdown anders gelesen/)).toBeInTheDocument()
    expect(screen.getByText(/Block 2 \(„Zweiter Absatz“\)/)).toBeInTheDocument()
    expect(connections[0]!.destroyed).toBe(false)
    expect(await screen.findByRole('textbox', { name: 'Inhalt von „Handbuch“' })).toHaveAttribute(
      'contenteditable',
      'true',
    )
    // Leaving asks first: the latest edits are not stored.
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    act(() => void router.navigate({ to: '/spaces/$spaceId', params: { spaceId: space.id } }))
    await waitFor(() => expect(confirm).toHaveBeenCalled())
    expect(router.state.location.search).toEqual({ view: 'live' })
    confirm.mockRestore()
    act(() => connections[0]!.handlers.onUnrepresentable(null))
    expect(screen.queryByText(/lässt sich so nicht als Markdown speichern/)).not.toBeInTheDocument()
  })

  test('leaving before a change is stored asks first, until the server acknowledges it (T5)', async () => {
    const current = makePage({ space_id: space.id, content_md: 'Alter Text' })
    liveApi('editor', () => current)
    const { router } = await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    const connection = connections[0]!
    join(connection)
    // Sent at once (nothing unsynced), not yet stored: the save comes seconds later, and a
    // state the server refuses is never stored.
    typeInto(connection.doc, 'neuer Satz')
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    act(() => void router.navigate({ to: '/spaces/$spaceId', params: { spaceId: space.id } }))
    await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1))
    expect(router.state.location.search).toEqual({ view: 'live' })
    // The server stored it and says so: leaving asks nothing.
    act(() => connection.handlers.onStored(Y.encodeSnapshot(Y.snapshot(connection.doc))))
    act(() => void router.navigate({ to: '/spaces/$spaceId', params: { spaceId: space.id } }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/spaces/${space.id}`))
    expect(confirm).toHaveBeenCalledTimes(1)
    confirm.mockRestore()
  })

  test('"Fertig" does not leave while the latest change is not acknowledged as stored', async () => {
    const current = makePage({ space_id: space.id, content_md: 'Alter Text' })
    liveApi('editor', () => current)
    fake.acknowledge = false // the server answers "saved" but its snapshot lacks the change
    const { router, user } = await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    join(connections[0]!)
    typeInto(connections[0]!.doc, 'neuer Satz')
    await user.click(screen.getByRole('button', { name: 'Fertig' }))
    expect(await screen.findByText(/noch nicht gespeichert/)).toBeInTheDocument()
    expect(router.state.location.search).toEqual({ view: 'live' })
  })

  test('a viewer gets the read-only page without a live connection', async () => {
    const current = makePage({ space_id: space.id, content_md: '# Handbuch\n\nNur lesen.' })
    liveApi('viewer', () => current)
    await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    expect(await screen.findByText('Nur lesen.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Gemeinsam bearbeiten' })).not.toBeInTheDocument()
    expect(connections).toHaveLength(0)
  })
})
