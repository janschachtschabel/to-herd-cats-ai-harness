// Ported-from: to-herd-cats-ai@46352bb:frontend/src/features/wiki/markdown-utils.ts
export interface Heading {
  level: 1 | 2 | 3
  text: string
  id: string
}

const UMLAUTS: Record<string, string> = { ä: 'ae', ö: 'oe', ü: 'ue', ß: 'ss' }
const FENCE = /^\s*(```|~~~)/

export function headingId(text: string): string {
  return text
    .toLowerCase()
    .replace(/[äöüß]/g, (c) => UMLAUTS[c] ?? c)
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

/** Lines of the Markdown with whether each lies inside a fenced code block. */
function lines(markdown: string): { line: string; code: boolean }[] {
  let inFence = false
  return markdown.split('\n').map((line) => {
    const fence = FENCE.test(line)
    if (fence) inFence = !inFence
    return { line, code: inFence || fence }
  })
}

/** h1–h3 outside fenced code blocks, in document order (the table of contents). */
export function extractHeadings(markdown: string): Heading[] {
  return lines(markdown).flatMap(({ line, code }) => {
    if (code) return []
    const match = /^(#{1,3})\s+(.+?)\s*#*\s*$/.exec(line)
    if (!match) return []
    const text = match[2] ?? ''
    return [{ level: match[1]!.length as 1 | 2 | 3, text, id: headingId(text) }]
  })
}

/** `[[Title]]` → a link to the page of that title (`wiki:<path>`), or to
 *  `wiki-missing:<title>` when no page has it. Fenced code is left alone. */
export function resolveWikiLinks(markdown: string, lookup: Map<string, string>): string {
  return lines(markdown)
    .map(({ line, code }) =>
      code
        ? line
        : line.replace(/\[\[([^\]\n]+)\]\]/g, (_, raw: string) => {
            const title = raw.trim()
            const path = lookup.get(title.toLowerCase())
            return path
              ? `[${title}](wiki:${encodeURIComponent(path)})`
              : `[${title}](wiki-missing:${encodeURIComponent(title)})`
          }),
    )
    .join('\n')
}

const ALLOWED_PROTOCOLS = new Set(['http:', 'https:', 'mailto:'])

/** Links and images only to http, https, mailto and relative targets; anything else
 *  (javascript:, data:, …) becomes '' and is rendered as plain text. */
export function safeUrl(url: string): string {
  const trimmed = url.trim()
  const colon = trimmed.indexOf(':')
  const firstStop = trimmed.search(/[/?#]/)
  const relative = colon === -1 || (firstStop !== -1 && firstStop < colon)
  if (relative) return trimmed
  return ALLOWED_PROTOCOLS.has(trimmed.slice(0, colon + 1).toLowerCase()) ? trimmed : ''
}
