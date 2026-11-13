import { act, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import * as Y from 'yjs'
import type { SpaceRole, WikiPage } from '@/lib/api'
import { makeMe, makePage, makeSpace, mockApi, nodeOf, page } from '@/test/api'
import { renderApp } from '@/test/render'
import type { LiveHandlers } from './connect'

/** The fake provider: every connection the editor opens, with its handlers. */
interface FakeConnection {
  pageId: string
  generation: number
  doc: Y.Doc
  handlers: LiveHandlers
  destroyed: boolean
}
const connections: FakeConnection[] = []

vi.mock('./connect', async (original) => ({
  ...(await original<typeof import('./connect')>()),
  connectLive: (options: Omit<FakeConnection, 'destroyed'>) => {
    const connection = { ...options, destroyed: false }
    connections.push(connection)
    return { provider: null, clientId: 1, destroy: () => void (connection.destroyed = true) }
  },
}))

const space = makeSpace({ name: 'Handbuch' })

function liveApi(role: SpaceRole, current: () => WikiPage) {
  const roleSpace = { ...space, my_role: role }
  return mockApi({
    'GET /api/auth/me': makeMe([]),
    'GET /api/spaces': page([roleSpace]),
    'GET /api/spaces/:id': roleSpace,
    'GET /api/spaces/:id/pages/tree': () => page([nodeOf(current())]),
    'GET /api/spaces/:id/pages/by-path': () => current(),
    'GET /api/pages/:id': () => current(),
    'GET /api/tags': page([]),
    'GET /api/pages/:id/attachments': page([]),
  })
}

/** The server's side of a connection: connected and synced. */
function join(connection: FakeConnection) {
  act(() => {
    connection.handlers.onConnected(true)
    connection.handlers.onSynced()
  })
}

function typeInto(doc: Y.Doc, text: string) {
  act(() => {
    const paragraph = new Y.XmlElement('paragraph')
    paragraph.insert(0, [new Y.XmlText(text)])
    doc.getXmlFragment('default').push([paragraph])
  })
}

beforeEach(() => {
  connections.length = 0
})

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
  })

  test('4422: a page the live editor would change is offered in the Markdown editor', async () => {
    const current = makePage({ space_id: space.id, content_md: '- a\n\n* b' })
    liveApi('editor', () => current)
    const { router, user } = await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    act(() => connections[0]!.handlers.onClose(4422))
    expect(
      await screen.findByText(/die der Live-Editor nicht unverändert bearbeiten kann/),
    ).toBeInTheDocument()
    expect(connections[0]!.destroyed).toBe(true)
    expect(screen.queryByRole('button', { name: 'Neu laden' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Im Markdown-Editor bearbeiten' }))
    await waitFor(() => expect(router.state.location.search).toEqual({ view: 'edit' }))
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

  test('a viewer gets the read-only page without a live connection', async () => {
    const current = makePage({ space_id: space.id, content_md: '# Handbuch\n\nNur lesen.' })
    liveApi('viewer', () => current)
    await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    expect(await screen.findByText('Nur lesen.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Gemeinsam bearbeiten' })).not.toBeInTheDocument()
    expect(connections).toHaveLength(0)
  })
})
