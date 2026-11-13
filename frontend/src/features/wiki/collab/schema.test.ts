import { Editor, Extension, getSchema, Node } from '@tiptap/core'
import { MarkdownManager } from '@tiptap/markdown'
import { describe, expect, test } from 'vitest'
import { allowedUri, extensions, keepWikiLinks, RAW_MARKDOWN } from '@collab/schema.mjs'
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
    const [starterKit, codeBlock] = extensions()
    expect(starterKit).toBeInstanceOf(Extension)
    expect(codeBlock).toBeInstanceOf(Node)
  })

  test('Markdown written in the browser is what the server writes', () => {
    const manager = new MarkdownManager({ extensions: extensions() })
    const markdown = '# Titel\n\n- [x] fertig [[Seite]]\n\n```raw-markdown\n<div>roh</div>\n```'
    expect(keepWikiLinks(manager.serialize(manager.parse(markdown)).trim())).toBe(
      '# Titel\n\n- [x] fertig [[Seite]]\n\n<div>roh</div>',
    )
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
