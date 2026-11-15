import { Editor } from '@tiptap/core'
import { afterEach, expect, test } from 'vitest'
import { extensions } from '@collab/schema.mjs'

// Images the page view does not show (`safeUrl`: only http, https, mailto and relative
// sources) are not shown in the live editor either (review M2 T11).
let editor: Editor | null = null
afterEach(() => {
  editor?.destroy()
  editor = null
})

function fresh() {
  editor = new Editor({ element: document.createElement('div'), extensions: extensions() })
  return editor
}

const images = (e: Editor) => {
  const found: string[] = []
  e.state.doc.descendants((node) => {
    if (node.type.name === 'image') found.push(String(node.attrs.src))
  })
  return found
}

test('pasted images keep only sources the page view shows', () => {
  const e = fresh()
  e.view.pasteHTML(
    '<p>Screenshot: <img src="blob:https://app.example/1" alt="eins"> und ' +
      '<img src="file:///C:/bild.png" alt="zwei"> und ' +
      '<img src="https://example.com/a.png" alt="drei"> und ' +
      '<img src="/bilder/b.png" alt="vier"> ende</p>',
    new Event('paste') as ClipboardEvent,
  )
  expect(images(e)).toEqual(['https://example.com/a.png', '/bilder/b.png'])
})

/** Typing as the view does: the text, then its last character through the view's text
 *  input handler, where input rules run (as when a person types the closing `)`). */
function typed(e: Editor, text: string) {
  e.commands.insertContent(text.slice(0, -1))
  const { from, to } = e.state.selection
  const last = text.slice(-1)
  const handled = e.view.someProp('handleTextInput', (handle) =>
    handle(e.view, from, to, last, () => e.state.tr.insertText(last, from, to)),
  )
  if (!handled) e.view.dispatch(e.state.tr.insertText(last, from, to))
}

test('a typed image with a source the page view does not show stays text', () => {
  const e = fresh()
  typed(e, '![bild](file:///tmp/x.png)')
  expect(images(e)).toEqual([])
  expect(e.getText()).toBe('![bild](file:///tmp/x.png)')
  typed(e, ' ![bild](/x.png)')
  expect(images(e)).toEqual(['/x.png'])
})

// Review M2 U13: an image whose source the page view does not show can still arrive in
// the shared document from another client; the editor does not load it either.
test('an image with a source the page view does not show is drawn without it', () => {
  const e = fresh()
  e.commands.setContent({
    type: 'doc',
    content: [
      {
        type: 'paragraph',
        content: [
          { type: 'image', attrs: { src: 'data:image/png;base64,AAAA', alt: 'eins' } },
          { type: 'image', attrs: { src: 'javascript:alert(1)', alt: 'zwei' } },
          { type: 'image', attrs: { src: '/bilder/b.png', alt: 'drei' } },
        ],
      },
    ],
  })
  const drawn = [...e.view.dom.querySelectorAll('img:not(.ProseMirror-separator)')].map((img) => [
    img.getAttribute('alt'),
    img.getAttribute('src'),
  ])
  expect(drawn).toEqual([
    ['eins', null],
    ['zwei', null],
    ['drei', '/bilder/b.png'],
  ])
})
