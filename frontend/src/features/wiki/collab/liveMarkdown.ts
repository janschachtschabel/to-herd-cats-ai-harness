import { yXmlFragmentToProsemirrorJSON } from '@tiptap/y-tiptap'
import type * as Y from 'yjs'
import { jsonToMarkdown } from '@collab/serialize.mjs'

const FIELD = 'default' // the fragment the collab process converts (collab/markdown.mjs)

/** The document as the collab process would save it, for copying text that could not
 *  be saved any more. */
export function liveMarkdown(doc: Y.Doc): string {
  return jsonToMarkdown(yXmlFragmentToProsemirrorJSON(doc.getXmlFragment(FIELD)))
}
