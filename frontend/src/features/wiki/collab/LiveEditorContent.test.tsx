import { act, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import * as Y from 'yjs'
import { makePage } from '@/test/api'
import { renderApp } from '@/test/render'
import { fake, join, liveApi, space } from './fakeLive.test-helper'

const { connections } = fake

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
})
