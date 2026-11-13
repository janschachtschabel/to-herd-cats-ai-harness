import { Extension, getSchema, Node } from '@tiptap/core'
import { MarkdownManager } from '@tiptap/markdown'
import { describe, expect, test } from 'vitest'
import { extensions, RAW_MARKDOWN } from '@collab/schema.mjs'
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
    const markdown = '# Titel\n\n- [x] fertig\n\n```raw-markdown\n<div>roh</div>\n```'
    expect(manager.serialize(manager.parse(markdown)).trim()).toBe(
      '# Titel\n\n- [x] fertig\n\n<div>roh</div>',
    )
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
