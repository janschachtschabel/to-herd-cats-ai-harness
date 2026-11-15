// The fake live connection of the live editor's tests: every connection the editor
// opens, with its handlers, and what the server answers to "I am done".
import { act } from '@testing-library/react'
import * as Y from 'yjs'
import type { SpaceRole, WikiPage } from '@/lib/api'
import { makeMe, makeSpace, mockApi, nodeOf, page } from '@/test/api'
import type { LiveConnection, LiveHandlers } from './connect'

export interface FakeConnection {
  pageId: string
  generation: number
  doc: Y.Doc
  handlers: LiveHandlers
  destroyed: boolean
}

export const fake = {
  connections: [] as FakeConnection[],
  events: [] as string[],
  /** What the server answers to "I am done" (true: everything is stored). */
  finishAnswer: (() => true) as () => boolean,
  /** Whether a save the server answers as done acknowledges the document's state. */
  acknowledge: true,
  reset() {
    fake.connections.length = 0
    fake.events.length = 0
    fake.finishAnswer = () => true
    fake.acknowledge = true
  },
}

export function fakeConnectLive(options: Omit<FakeConnection, 'destroyed'>): LiveConnection {
  const connection = { ...options, destroyed: false }
  fake.connections.push(connection)
  const destroy = () => void (connection.destroyed = true)
  const finish = async () => {
    await new Promise((resolve) => setTimeout(resolve, 20)) // the server confirms
    fake.events.push('flushed')
    const saved = fake.finishAnswer()
    // The server acknowledges what it stored before it answers (collab/documents.mjs).
    if (saved && fake.acknowledge) {
      connection.handlers.onStored(Y.encodeSnapshot(Y.snapshot(connection.doc)))
    }
    return saved
  }
  const reportLoadMutation = () => void fake.events.push('load-mutation')
  return { provider: null, clientId: 1, destroy, finish, reportLoadMutation }
}

export const space = makeSpace({ name: 'Handbuch' })

export function liveApi(role: SpaceRole, current: () => WikiPage) {
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
export function join(connection: FakeConnection) {
  act(() => {
    connection.handlers.onConnected(true)
    connection.handlers.onSynced()
  })
}

export function typeInto(doc: Y.Doc, text: string) {
  act(() => {
    const paragraph = new Y.XmlElement('paragraph')
    paragraph.insert(0, [new Y.XmlText(text)])
    doc.getXmlFragment('default').push([paragraph])
  })
}
