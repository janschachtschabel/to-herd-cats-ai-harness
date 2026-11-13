import { Editor, getSchema, type JSONContent } from '@tiptap/core'
import { prosemirrorJSONToYDoc } from '@tiptap/y-tiptap'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test } from 'vitest'
import { FIELD, liveExtensions } from '@collab/editor.mjs'
import { extensions } from '@collab/schema.mjs'
import { jsonToMarkdown } from '@collab/serialize.mjs'
import { Toolbar } from './Toolbar'

// A link can be taken off in the editor (review M2 U5): a toolbar button, enabled while
// the caret is in a link, reachable with the keyboard.
let editor: Editor | null = null
afterEach(() => {
  editor?.destroy()
  editor = null
})

const LINKED: JSONContent = {
  type: 'doc',
  content: [
    {
      type: 'paragraph',
      content: [
        { type: 'text', text: 'Siehe ' },
        {
          type: 'text',
          text: 'README.md',
          marks: [{ type: 'link', attrs: { href: 'http://README.md' } }],
        },
        { type: 'text', text: ' hier' },
      ],
    },
  ],
}

/** The live editor on a shared document holding a link. */
function withLink() {
  const document = prosemirrorJSONToYDoc(getSchema(extensions()), LINKED, FIELD)
  editor = new Editor({
    element: window.document.createElement('div'),
    extensions: liveExtensions({ document }),
  })
  return editor
}

test('the link at the caret is taken off', async () => {
  const e = withLink()
  e.commands.setTextSelection(10) // inside "README.md", nothing selected
  render(<Toolbar editor={e} disabled={false} />)
  const unlink = screen.getByRole('button', { name: 'Link entfernen' })
  expect(unlink).toBeEnabled()
  await userEvent.click(unlink)
  expect(jsonToMarkdown(e.getJSON())).toBe('Siehe README.md hier')
  expect(screen.getByRole('button', { name: 'Link entfernen' })).toBeDisabled()
})

test('outside a link there is nothing to take off', () => {
  const e = withLink()
  e.commands.setTextSelection(3)
  render(<Toolbar editor={e} disabled={false} />)
  expect(screen.getByRole('button', { name: 'Link entfernen' })).toBeDisabled()
})

test('the button is reached with the keyboard', async () => {
  const e = withLink()
  e.commands.setTextSelection(10)
  render(<Toolbar editor={e} disabled={false} />)
  const unlink = screen.getByRole('button', { name: 'Link entfernen' })
  unlink.focus()
  await userEvent.keyboard('{Enter}')
  expect(jsonToMarkdown(e.getJSON())).toBe('Siehe README.md hier')
})
