// Types of the collab process's shared schema (../../../../../collab/schema.mjs, plain
// ESM), imported through the `@collab` alias of vite.config.ts.
declare module '@collab/schema.mjs' {
  import type { AnyExtension } from '@tiptap/core'

  export const RAW_MARKDOWN: string
  export function extensions(): AnyExtension[]
}
