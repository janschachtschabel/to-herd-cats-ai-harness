import Collaboration from '@tiptap/extension-collaboration'
import CollaborationCaret from '@tiptap/extension-collaboration-caret'
import { EditorContent, useEditor } from '@tiptap/react'
import { useEffect } from 'react'
import type * as Y from 'yjs'
import { extensions } from '@collab/schema.mjs'
import type { LiveConnection } from './connect'
import { Toolbar } from './Toolbar'

const FIELD = 'default' // the Y.XmlFragment the collab process reads (collab/markdown.mjs)

/** The visual editor on the page's Y.Doc, with the collab process's own schema (so
 *  what is typed here is exactly what the server can write as Markdown) and the other
 *  people's cursors. */
export function LiveSurface({
  doc,
  connection,
  editable,
  label,
  userName,
}: {
  doc: Y.Doc
  connection: LiveConnection | null
  editable: boolean
  label: string
  userName: string
}) {
  const provider = connection?.provider ?? null
  const editor = useEditor(
    {
      extensions: [
        ...extensions(),
        Collaboration.configure({ document: doc, field: FIELD }),
        ...(provider
          ? [CollaborationCaret.configure({ provider, user: { name: userName, color: '#64748b' } })]
          : []),
      ],
      editable,
      editorProps: {
        attributes: {
          'aria-label': label,
          'aria-multiline': 'true',
          role: 'textbox',
          class: 'min-h-[24rem] px-4 py-3 outline-none',
        },
      },
    },
    [doc, provider],
  )
  useEffect(() => {
    editor?.setEditable(editable)
  }, [editor, editable])
  if (!editor) return null
  return (
    <div className="wiki-editor rounded-lg border focus-within:ring-2 focus-within:ring-ring/50">
      <Toolbar editor={editor} disabled={!editable} />
      <EditorContent editor={editor} />
    </div>
  )
}
