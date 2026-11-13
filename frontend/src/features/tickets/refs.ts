/** Ticket keys in text (plan M4, decision 1): the fixed prefix `HC` and the number,
 *  as the server writes `key`. Addresses use the number (`/tickets/42`). */
export const TICKET_PREFIX = 'HC'

export const ticketKey = (number: number) => `${TICKET_PREFIX}-${number}`

/** The cards one message shows at most (plan M4, Task 7). */
export const MAX_CARDS = 3

const KEY = new RegExp(`(?<![\\w/-])${TICKET_PREFIX}-(\\d{1,9})(?![\\w-])`, 'gi')
const LINK = /(?:^|[\s(<[])(?:https?:\/\/[^\s/]+)?\/tickets\/(\d{1,9})(?![\w-])/gi
const CODE = /```[\s\S]*?```|`[^`\n]*`/g

/** The tickets a message names, by key (`HC-42`) or by a link to `/tickets/42`, each
 *  once and in order, at most MAX_CARDS; text in code is not a mention. */
export function ticketRefs(markdown: string): number[] {
  const text = markdown.replace(CODE, ' ')
  const found: { at: number; number: number }[] = []
  for (const match of text.matchAll(KEY)) found.push({ at: match.index, number: Number(match[1]) })
  for (const match of text.matchAll(LINK)) found.push({ at: match.index, number: Number(match[1]) })
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
