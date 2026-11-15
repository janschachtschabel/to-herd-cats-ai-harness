import CollaborationCaret from '@tiptap/extension-collaboration-caret'
import { EditorContent, useEditor } from '@tiptap/react'
import { useEffect } from 'react'
import type * as Y from 'yjs'
import { FIELD, liveExtensions } from '@collab/editor.mjs'
import type { LiveConnection } from './connect'
import { Toolbar } from './Toolbar'

/** The visual editor on the page's Y.Doc, with the collab process's own editor (so what
 *  is typed here is exactly what the server can write as Markdown, and the server knows
 *  what this editor does on loading) and the other people's cursors. */
export function LiveSurface({
  doc,
  connection,
  editable,
  label,
  userName,
  onContentError,
  onLoadMutation,
}: {
  doc: Y.Doc
  connection: LiveConnection | null
  editable: boolean
  label: string
  userName: string
  /** The shared document holds what the schema does not allow (review M2 S1). */
  onContentError: () => void
  /** The editor changed the document it had just loaded before the person did anything
   *  (review M2 ruling B): the change was not applied, so nothing was sent. */
  onLoadMutation: () => void
}) {
  const provider = connection?.provider ?? null
  const editor = useEditor(
    {
      extensions: [
        ...liveExtensions({
          document: doc,
          field: FIELD,
          onLoadMutation: () => {
            // Not from inside the editor's transaction: stop right after it.
            queueMicrotask(onLoadMutation)
            return false
          },
        }),
        ...(provider
          ? [CollaborationCaret.configure({ provider, user: { name: userName, color: '#64748b' } })]
          : []),
      ],
      editable,
      // Content the schema does not allow is never repaired into the shared document
      // (the repair would be saved): the session stops instead.
      enableContentCheck: true,
      onContentError: ({ disableCollaboration }) => {
        onContentError()
        disableCollaboration()
      },
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
