import { MarkdownManager } from '@tiptap/markdown'
import { yXmlFragmentToProsemirrorJSON } from '@tiptap/y-tiptap'
import type * as Y from 'yjs'
import { extensions } from '@collab/schema.mjs'

const FIELD = 'default' // the fragment the collab process converts (collab/markdown.mjs)

let manager: MarkdownManager | null = null

/** The document as the collab process would save it, for copying text that could not
 *  be saved any more. */
export function liveMarkdown(doc: Y.Doc): string {
  manager ??= new MarkdownManager({ extensions: extensions() })
  const json = yXmlFragmentToProsemirrorJSON(doc.getXmlFragment(FIELD))
  return manager.serialize(json).replace(/^\n+|\n+$/g, '')
}
