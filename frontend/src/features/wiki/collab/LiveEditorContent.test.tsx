import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import type { Editor } from '@tiptap/core'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import * as Y from 'yjs'
import { makePage } from '@/test/api'
import { renderApp } from '@/test/render'
import { fake, join, liveApi, space } from './fakeLive.test-helper'

const { connections } = fake

/** A table whose second row is shorter than the header, as an older collab process
 *  built it: the browser's table repair widens it on loading. */
function raggedTable(doc: Y.Doc) {
  const cell = (type: string, text: string) => {
    const element = new Y.XmlElement(type)
    const paragraph = new Y.XmlElement('tableParagraph')
    paragraph.insert(0, [new Y.XmlText(text)])
    element.insert(0, [paragraph])
    return element
  }
  const row = (...cells: Y.XmlElement[]) => {
    const element = new Y.XmlElement('tableRow')
    element.insert(0, cells)
    return element
  }
  const table = new Y.XmlElement('table')
  table.insert(0, [
    row(cell('tableHeader', 'a'), cell('tableHeader', 'b')),
    row(cell('tableCell', '1')),
  ])
  doc.getXmlFragment('default').push([table])
  return table
}

vi.mock('./connect', async (original) => ({
  ...(await original<typeof import('./connect')>()),
  connectLive: (await import('./fakeLive.test-helper')).fakeConnectLive,
}))

beforeEach(() => fake.reset())

describe('live editor content', () => {
  test('a shared document the schema does not allow closes the session unrepaired (review S1)', async () => {
    const current = makePage({ space_id: space.id, content_md: 'Text' })
    liveApi('editor', () => current)
    await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    const connection = connections[0]!
    join(connection)
    await screen.findByRole('textbox', { name: 'Inhalt von „Handbuch“' })
    // A paragraph holding a block: the editor would drop it, and that deletion would
    // be synced and saved.
    act(() => {
      const paragraph = new Y.XmlElement('paragraph')
      paragraph.insert(0, [new Y.XmlElement('horizontalRule')])
      connection.doc.getXmlFragment('default').push([paragraph])
    })
    expect(await screen.findByText(/nicht darstellen/)).toBeInTheDocument()
    expect(connection.destroyed).toBe(true)
    expect(connection.doc.getXmlFragment('default').length).toBe(1)
    expect(screen.queryByRole('button', { name: 'Neu laden' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Im Markdown-Editor bearbeiten' })).toBeInTheDocument()
  })

  test('a change the editor makes to a document it just loaded is never sent: it stops (ruling B)', async () => {
    const current = makePage({ space_id: space.id, content_md: '' })
    liveApi('editor', () => current)
    await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    const connection = connections[0]!
    join(connection)
    await screen.findByRole('textbox', { name: 'Inhalt von „Handbuch“' })
    const sent: Uint8Array[] = []
    connection.doc.on('update', (update: Uint8Array, origin: unknown) => {
      if (origin !== 'server') sent.push(update)
    })
    let table: Y.XmlElement | null = null
    act(() => {
      connection.doc.transact(() => (table = raggedTable(connection.doc)), 'server')
    })
    expect(await screen.findByText(/nicht darstellen/)).toBeInTheDocument()
    expect(fake.events).toContain('load-mutation')
    expect(connection.destroyed).toBe(true)
    expect(sent).toEqual([])
    expect((table!.get(1) as Y.XmlElement).length).toBe(1) // not repaired
    expect(screen.getByRole('link', { name: 'Im Markdown-Editor bearbeiten' })).toBeInTheDocument()
  })

  test("once the person did something, the editor's own changes are synced as usual", async () => {
    const current = makePage({ space_id: space.id, content_md: '' })
    liveApi('editor', () => current)
    await renderApp(`/spaces/${space.id}/p/handbuch?view=live`)
    await waitFor(() => expect(connections).toHaveLength(1))
    const connection = connections[0]!
    join(connection)
    const editor = await screen.findByRole('textbox', { name: 'Inhalt von „Handbuch“' })
    fireEvent.keyDown(editor, { key: 'Shift' })
    let table: Y.XmlElement | null = null
    act(() => {
      connection.doc.transact(() => (table = raggedTable(connection.doc)), 'server')
    })
    // The binding writes the editor's changes on its next transaction (a cursor, focus).
    act(() => {
      const { editor: instance } = editor as unknown as { editor: Editor }
      instance.view.dispatch(instance.state.tr)
    })
    await waitFor(() => expect((table!.get(1) as Y.XmlElement).length).toBe(2))
    expect(connection.destroyed).toBe(false)
    expect(fake.events).not.toContain('load-mutation')
  })
})
