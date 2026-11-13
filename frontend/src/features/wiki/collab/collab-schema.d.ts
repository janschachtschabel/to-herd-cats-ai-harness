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
