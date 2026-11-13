import { fromMarkdown } from 'mdast-util-from-markdown'
import { gfmFromMarkdown } from 'mdast-util-gfm'
import { gfm } from 'micromark-extension-gfm'

/** Ticket keys in text (plan M4, decision 1): the fixed prefix `HC` and the number,
 *  as the server writes `key`. Addresses use the number (`/tickets/42`). */
export const TICKET_PREFIX = 'HC'

export const ticketKey = (number: number) => `${TICKET_PREFIX}-${number}`

/** The cards one message shows at most (plan M4, Task 7). */
export const MAX_CARDS = 3

const KEY = new RegExp(`(?<![\\w/-])${TICKET_PREFIX}-(\\d{1,9})(?![\\w-])`, 'gi')
const LINK = /(?:^|[\s(<[])(?:https?:\/\/[^\s/]+)?\/tickets\/(\d{1,9})(?![\w-])/gi
const LINK_URL = /^(?:https?:\/\/[^\s/]+)?\/tickets\/(\d{1,9})(?:[?#].*)?$/i

/** The parts of a Markdown tree the search reads (mdast, structurally). */
type MdNode = {
  type: string
  value?: string
  url?: string
  children?: MdNode[]
  position?: { start: { offset?: number } }
}
type Found = { at: number; number: number }

/** Keys and ticket paths in the plain text of the tree, and the targets of links:
 *  code of any kind (inline, fenced, indented), raw HTML, images and the text of a
 *  link are not read; a link counts only when it points at a ticket. */
function collect(node: MdNode, found: Found[]) {
  const at = node.position?.start.offset ?? 0
  if (node.type === 'text' && node.value) {
    for (const match of node.value.matchAll(KEY))
      found.push({ at: at + match.index, number: Number(match[1]) })
    for (const match of node.value.matchAll(LINK))
      found.push({ at: at + match.index, number: Number(match[1]) })
    return
  }
  if (node.type === 'link' || node.type === 'linkReference') {
    const match = node.url ? LINK_URL.exec(node.url) : null
    if (match) found.push({ at, number: Number(match[1]) })
    return
  }
  for (const child of node.children ?? []) collect(child, found)
}

/** The tickets a message names, by key (`HC-42`) or by a link to `/tickets/42`, each
 *  once and in order, at most MAX_CARDS. Read from the Markdown tree the message is
 *  shown from (GFM, as `MessageMarkdown`): text in code or in a link is not a mention
 *  (review M4 P5). */
export function ticketRefs(markdown: string): number[] {
  const found: Found[] = []
  collect(
    fromMarkdown(markdown, { extensions: [gfm()], mdastExtensions: [gfmFromMarkdown()] }),
    found,
  )
  const numbers: number[] = []
  for (const { number } of found.sort((a, b) => a.at - b.at)) {
    if (number > 0 && !numbers.includes(number)) numbers.push(number)
    if (numbers.length === MAX_CARDS) break
  }
  return numbers
}

/** A search input that is a ticket key (`HC-42`, `hc-42`, `42`): its number. */
export function keyNumber(input: string): number | null {
  const match = new RegExp(`^\\s*(?:${TICKET_PREFIX}-)?(\\d{1,9})\\s*$`, 'i').exec(input)
  return match ? Number(match[1]) : null
}
