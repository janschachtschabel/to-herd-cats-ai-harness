import { useTranslation } from 'react-i18next'
import type { Schemas } from '@/lib/api'
import { cn } from '@/lib/utils'

type Hunk = Schemas['HunkOut']

const MARK = { insert: '+', delete: '−', equal: ' ' } as const

/** Diff lines as `<ins>` and `<del>`: a visible + or − beside each changed line, its
 *  kind said to screen readers, and the colour only as a third cue. */
export function DiffLines({ hunks }: { hunks: readonly Hunk[] }) {
  const { t } = useTranslation()
  return (
    <pre className="overflow-x-auto rounded-lg border text-xs leading-5">
      {hunks.flatMap((hunk, h) =>
        hunk.lines.map((line, i) => {
          const Tag = hunk.kind === 'insert' ? 'ins' : hunk.kind === 'delete' ? 'del' : 'div'
          return (
            <Tag
              key={`${h}-${i}`}
              className={cn(
                'block px-3 whitespace-pre-wrap no-underline',
                hunk.kind === 'insert' && 'bg-emerald-500/15',
                hunk.kind === 'delete' && 'bg-red-500/15',
              )}
            >
              <span aria-hidden className="mr-2 text-muted-foreground select-none">
                {MARK[hunk.kind]}
              </span>
              {hunk.kind !== 'equal' && (
                <span className="sr-only">{t(`wiki.versions.kind.${hunk.kind}`)} </span>
              )}
              {line}
            </Tag>
          )
        }),
      )}
    </pre>
  )
}
