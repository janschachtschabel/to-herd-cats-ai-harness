const START = '⟦'
const STOP = '⟧'

/** A search snippet with the server's markers `⟦…⟧` shown as <mark>; everything is
 *  rendered as text, so HTML in a snippet is never interpreted. */
export function Highlight({ snippet }: { snippet: string }) {
  const parts: { text: string; hit: boolean }[] = []
  let rest = snippet
  while (rest) {
    const start = rest.indexOf(START)
    if (start === -1) {
      parts.push({ text: rest, hit: false })
      break
    }
    const stop = rest.indexOf(STOP, start + 1)
    if (stop === -1) {
      parts.push({ text: rest.replace(START, ''), hit: false })
      break
    }
    if (start > 0) parts.push({ text: rest.slice(0, start), hit: false })
    parts.push({ text: rest.slice(start + 1, stop), hit: true })
    rest = rest.slice(stop + 1)
  }
  return (
    <>
      {parts.map((part, i) =>
        part.hit ? (
          <mark
            key={i}
            className="rounded-sm bg-yellow-200 px-0.5 text-foreground dark:bg-yellow-500/40"
          >
            {part.text}
          </mark>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </>
  )
}
