import * as Y from 'yjs'

const NOTICE = 'herd:unrepresentable'
const KINDS = ['structure', 'reopen', 'markdown', 'tooLarge'] as const
const DETAILS = ['tableCode', 'address', 'list'] as const
const START_LENGTH = 40

/** Why the latest state cannot be saved, and where, as far as the save check knows it
 *  (collab/readback.mjs): `structure` (the editor cannot hold it), `reopen` (the
 *  Markdown would not open again unchanged), `markdown` (it reads back as something
 *  else), `tooLarge` (its tables hold more cells than live editing takes,
 *  collab/cells.mjs); `block` is the index of the top-level block, null when unknown; `through`
 *  the second of two neighbours that fail only together (review M2 U1), else null. */
export interface Unsaveable {
  kind: (typeof KINDS)[number] | 'unknown'
  block: number | null
  through: number | null
  /** The kind of difference for kind `markdown` (collab/cause.mjs), for an example that
   *  fits it (review M2 U12); null when not known. */
  detail: (typeof DETAILS)[number] | null
}

/** The notice the collab process sends (`herd:unrepresentable:<kind>:<where>[:<detail>]`,
 *  where is `<block>` or `<block>-<through>`), or null for any other message. */
export function unsaveable(payload: string): Unsaveable | null {
  if (payload !== NOTICE && !payload.startsWith(`${NOTICE}:`)) return null
  const [kind = '', where = '', detail = ''] = payload.slice(NOTICE.length + 1).split(':')
  const known = (KINDS as readonly string[]).includes(kind)
  const match = known ? /^(\d+)(?:-(\d+))?$/.exec(where) : null
  return {
    kind: known ? (kind as Unsaveable['kind']) : 'unknown',
    block: match ? Number(match[1]) : null,
    through: match?.[2] ? Number(match[2]) : null,
    detail: (DETAILS as readonly string[]).includes(detail)
      ? (detail as Unsaveable['detail'])
      : null,
  }
}

function textOf(node: Y.XmlElement | Y.XmlText | Y.XmlHook): string {
  if (node instanceof Y.XmlText) {
    return (node.toDelta() as { insert: unknown }[])
      .map(({ insert }) => (typeof insert === 'string' ? insert : ''))
      .join('')
  }
  if (node instanceof Y.XmlElement) {
    return node
      .toArray()
      .map((child) => textOf(child))
      .join(' ')
  }
  return ''
}

/** The start of the text of the document's top-level block `index` ('' if none). */
export function blockStart(doc: Y.Doc, index: number): string {
  const fragment = doc.getXmlFragment('default')
  if (index < 0 || index >= fragment.length) return ''
  const text = textOf(fragment.get(index)).replace(/\s+/g, ' ').trim()
  if (text.length <= START_LENGTH) return text
  const cut = text.slice(0, START_LENGTH + 1)
  const space = cut.lastIndexOf(' ')
  return `${space > START_LENGTH / 2 ? cut.slice(0, space) : cut.slice(0, START_LENGTH)} …`
}
