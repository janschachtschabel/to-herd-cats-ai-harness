// Types of the collab process's shared modules (../../../../../collab/*.mjs, plain ESM),
// imported through the `@collab` alias of vite.config.ts.
declare module '@collab/schema.mjs' {
  import type { AnyExtension } from '@tiptap/core'

  export const RAW_MARKDOWN: string
  export function extensions(): AnyExtension[]
  export function allowedUri(url: string): boolean
}

declare module '@collab/serialize.mjs' {
  import type { JSONContent } from '@tiptap/core'

  export function jsonToMarkdown(json: JSONContent): string
}

declare module '@collab/wikilinks.mjs' {
  export interface WikiLink {
    start: number
    end: number
    title: string
  }
  export function wikiLinks(markdown: string): WikiLink[]
  export function replaceWikiLinks(markdown: string, replace: (link: WikiLink) => string): string
  export function linkText(title: string): string
}

declare module '@collab/editor.mjs' {
  import type { AnyExtension, Editor } from '@tiptap/core'
  import type { Transaction } from '@tiptap/pm/state'
  import type * as Y from 'yjs'

  export const FIELD: string
  export function liveExtensions(options: {
    document: Y.Doc
    field?: string
    onLoadMutation?: (transaction: Transaction) => boolean
  }): AnyExtension[]
  export function markInput(editor: Editor): void
  export function hadInput(editor: Editor): boolean
}

declare module '@collab/tables.mjs' {
  export function flattenTableSpans<T extends ParentNode>(root: T): T
}

declare module '@collab/cells.mjs' {
  export const MAX_TABLE_CELLS: number
}
