import { Editor } from '@tiptap/core'
import { afterEach, expect, test } from 'vitest'
import { extensions } from '@collab/schema.mjs'
import { jsonToMarkdown } from '@collab/serialize.mjs'

// Typing links only what starts with http://, https:// or www. (review M2 U5): file
// names and domain-like words (`README.md`, `app.py`, `example.com`) stay text, as the
// page view shows them.
let editor: Editor | null = null
afterEach(() => {
  editor?.destroy()
  editor = null
})

/** Types character by character, each its own transaction (as a person types). */
function typeEach(e: Editor, text: string) {
  for (const char of text) {
    const { from, to } = e.state.selection
    e.view.dispatch(e.state.tr.insertText(char, from, to))
  }
}

function typedMarkdown(text: string) {
  editor = new Editor({ element: document.createElement('div'), extensions: extensions() })
  editor.commands.focus('end')
  typeEach(editor, text)
  return jsonToMarkdown(editor.getJSON())
}

test('file names and domain-like words stay text', () => {
  expect(typedMarkdown('Siehe README.md und app.py sowie example.com ')).toBe(
    'Siehe README.md und app.py sowie example.com',
  )
})

test('addresses with a scheme or www. are linked', () => {
  expect(typedMarkdown('Siehe https://example.com/a und www.example.org ')).toBe(
    'Siehe <https://example.com/a> und [www.example.org](http://www.example.org)',
  )
})

test('a pasted file name stays text', () => {
  editor = new Editor({ element: document.createElement('div'), extensions: extensions() })
  editor.view.pasteText('README.md und app.py', new Event('paste') as ClipboardEvent)
  expect(jsonToMarkdown(editor.getJSON())).toBe('README.md und app.py')
})
