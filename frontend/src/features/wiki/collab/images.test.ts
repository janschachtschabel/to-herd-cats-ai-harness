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

/** Input rules run on the next turn of the event loop after `insertContent`. */
const typed = async (e: Editor, text: string) => {
  e.commands.insertContent(text, { applyInputRules: true })
  await new Promise((resolve) => setTimeout(resolve, 0))
}

test('a typed image with a source the page view does not show stays text', async () => {
  const e = fresh()
  await typed(e, '![bild](file:///tmp/x.png)')
  expect(images(e)).toEqual([])
  expect(e.getText()).toBe('![bild](file:///tmp/x.png)')
  await typed(e, ' ![bild](/x.png)')
  expect(images(e)).toEqual(['/x.png'])
})
