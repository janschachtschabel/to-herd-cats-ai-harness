import { useTranslation } from 'react-i18next'
import type { Schemas } from '@/lib/api'
import { cn } from '@/lib/utils'
import { CATEGORIES, CATEGORY_DOT, childTotal } from './display'

type Counts = Schemas['ChildCounts']

/** How far a ticket's children are, as a bar of their categories and in words
 *  ("3 von 5 erledigt"; cancelled ones count as finished). */
export function Progress({ counts, className }: { counts: Counts; className?: string }) {
  const { t } = useTranslation()
  const total = childTotal(counts)
  if (total === 0) return null
  const finished = counts.done + counts.cancelled
  const label = t('tickets.progress.label', { done: finished, count: total })
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div
        role="img"
        aria-label={label}
        className="flex h-2 w-full overflow-hidden rounded-full bg-muted"
      >
        {CATEGORIES.map((category) =>
          counts[category] > 0 ? (
            <span
              key={category}
              className={cn('h-full', CATEGORY_DOT[category])}
              style={{ width: `${(counts[category] / total) * 100}%` }}
            />
          ) : null,
        )}
      </div>
      <p aria-hidden className="text-xs text-muted-foreground">
        {label}
      </p>
    </div>
  )
}
