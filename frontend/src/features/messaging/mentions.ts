/** Mentions in a message's Markdown are structured: `@[Name](user:<id>)` (plan M3,
 *  decision 4). The ids are sent along as `mentions`; the server decides who is told. */

const TOKEN = /@\[([^\]\n]*)\]\(user:([0-9a-fA-F-]{36})\)/g

/** What `@` starts while one is typing: up to 40 characters, no spaces or brackets. */
const TYPING = /(^|[\s(])@([^\s@[\]()]{0,40})$/

export interface Mentioned {
  id: string
  name: string
}

/** The token for a person; brackets in a name would end it early, so they go. */
export function mentionToken(person: Mentioned): string {
  return `@[${person.name.replace(/[[\]\n]/g, '')}](user:${person.id})`
}

/** The people a text mentions, each once, in order of appearance. */
export function mentionsIn(text: string): Mentioned[] {
  const seen = new Map<string, Mentioned>()
  for (const match of text.matchAll(TOKEN)) {
    const id = match[2]!.toLowerCase()
    if (!seen.has(id)) seen.set(id, { id, name: match[1]! })
  }
  return [...seen.values()]
}

/** The `@query` being typed just before `caret`, if any. */
export function typedMention(text: string, caret: number): { start: number; query: string } | null {
  const match = TYPING.exec(text.slice(0, caret))
  if (!match) return null
  const query = match[2] ?? ''
  return { start: caret - query.length - 1, query }
}

/** Replaces the typed `@query` (from `start` to `caret`) with the person's token. */
export function insertMention(
  text: string,
  start: number,
  caret: number,
  person: Mentioned,
): { text: string; caret: number } {
  const token = `${mentionToken(person)} `
  return {
    text: text.slice(0, start) + token + text.slice(caret),
    caret: start + token.length,
  }
}

/** A short text for lists and notices: mention tokens read as `@Name`. */
export function plainMentions(text: string): string {
  return text.replace(TOKEN, (_, name: string) => `@${name}`)
}
