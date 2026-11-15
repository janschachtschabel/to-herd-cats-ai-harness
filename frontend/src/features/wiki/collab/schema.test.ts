import { Editor, Extension, getSchema, Mark } from '@tiptap/core'
import { describe, expect, test } from 'vitest'
import { allowedUri, extensions, RAW_MARKDOWN } from '@collab/schema.mjs'
import { jsonToMarkdown } from '@collab/serialize.mjs'
import collabPackage from '../../../../../collab/package.json'
import frontendPackage from '../../../../package.json'

describe('the shared editor schema', () => {
  test('is the collab process module, with the nodes the server converts', () => {
    const schema = getSchema(extensions())
    for (const node of ['heading', 'codeBlock', 'image', 'table', 'taskList', 'taskItem']) {
      expect(schema.nodes[node], node).toBeDefined()
    }
    expect(schema.marks.link).toBeDefined()
    expect(schema.marks.underline).toBeUndefined()
    expect(RAW_MARKDOWN).toBe('raw-markdown')
  })

  test("resolves Tiptap from this project, not from collab's node_modules", () => {
    const [starterKit, code] = extensions()
    expect(starterKit).toBeInstanceOf(Extension)
    expect(code).toBeInstanceOf(Mark)
  })

  test('Markdown written in the browser is what the server writes', () => {
    const text = (value: string) => ({ type: 'text', text: value })
    const json = {
      type: 'doc',
      content: [
        { type: 'heading', attrs: { level: 1 }, content: [text('Titel')] },
        {
          type: 'taskList',
          content: [
            {
              type: 'taskItem',
              attrs: { checked: true },
              content: [{ type: 'paragraph', content: [text('fertig [[Seite]]')] }],
            },
          ],
        },
        { type: 'codeBlock', attrs: { language: RAW_MARKDOWN }, content: [text('<div>roh</div>')] },
      ],
    }
    // The document is valid for the editor and written as the server writes it.
    expect(() => getSchema(extensions()).nodeFromJSON(json).check()).not.toThrow()
    expect(jsonToMarkdown(json)).toBe('# Titel\n\n- [x] fertig [[Seite]]\n\n<div>roh</div>')
    expect(allowedUri('javascript:alert(1)')).toBe(false)
    expect(allowedUri('/spaces/x')).toBe(true)
    expect(allowedUri('mailto:a@b.de')).toBe(true)
  })

  test('opening a page adds nothing to its document', () => {
    // A trailing paragraph added by every browser that joins would be added once per
    // person (Yjs merges both) and saved as `&nbsp;` lines.
    const editor = new Editor({ extensions: extensions() })
    editor.commands.setContent({
      type: 'doc',
      content: [{ type: 'heading', attrs: { level: 1 }, content: [{ type: 'text', text: 'T' }] }],
    })
    expect(editor.state.doc.childCount).toBe(1)
    editor.destroy()
  })

  test('browser and collab process depend on the same Tiptap and Yjs versions', () => {
    const shared = Object.keys(collabPackage.dependencies).filter(
      (name) => name.startsWith('@tiptap/') || name === 'yjs',
    )
    const ours = frontendPackage.dependencies as Record<string, string>
    for (const name of shared) {
      expect(ours[name], name).toBe((collabPackage.dependencies as Record<string, string>)[name])
    }
  })
})
