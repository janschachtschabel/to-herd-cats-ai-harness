import type { Schemas } from '@/lib/api'

export type Hunk = Schemas['HunkOut']

/** Beyond this many line pairs the texts are shown as replaced (a skill is at most a
 *  few thousand lines; the table would grow past what a browser should hold). */
const MAX_CELLS = 4_000_000

function lines(text: string): string[] {
  return text === '' ? [] : text.split('\n')
}

function push(hunks: Hunk[], kind: Hunk['kind'], line: string): void {
  const last = hunks.at(-1)
  if (last && last.kind === kind) last.lines.push(line)
  else hunks.push({ kind, lines: [line] })
}

/** A line diff of two texts (longest common subsequence), as the wiki's diff hunks:
 *  equal runs, and deletions before insertions where lines were replaced. */
export function lineDiff(before: string, after: string): Hunk[] {
  const a = lines(before)
  const b = lines(after)
  const hunks: Hunk[] = []
  if (a.length * b.length > MAX_CELLS) {
    if (a.length) hunks.push({ kind: 'delete', lines: a })
    if (b.length) hunks.push({ kind: 'insert', lines: b })
    return hunks
  }
  // common[i][j]: the longest common run of a[i..] and b[j..].
  const width = b.length + 1
  const common = new Uint32Array((a.length + 1) * width)
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      common[i * width + j] =
        a[i] === b[j]
          ? common[(i + 1) * width + j + 1]! + 1
          : Math.max(common[(i + 1) * width + j]!, common[i * width + j + 1]!)
    }
  }
  let i = 0
  let j = 0
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      push(hunks, 'equal', a[i]!)
      i++
      j++
    } else if (common[(i + 1) * width + j]! >= common[i * width + j + 1]!) {
      push(hunks, 'delete', a[i++]!)
    } else {
      push(hunks, 'insert', b[j++]!)
    }
  }
  while (i < a.length) push(hunks, 'delete', a[i++]!)
  while (j < b.length) push(hunks, 'insert', b[j++]!)
  return hunks
}
