import { ClipboardCheck } from 'lucide-react'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import type { WikiPage } from '@/lib/api'
import { formatDay } from '@/lib/format'
import { useMarkReviewed } from '../queries'
import { useWiki } from '../WikiContext'
import { WikiError } from '../WikiError'

/** On a page whose review is due: when it was last reviewed, and for those who may edit
 *  it the button that starts its interval again. */
export function ReviewDueNotice({ page }: { page: WikiPage }) {
  const { t, i18n } = useTranslation()
  const { space, abilities } = useWiki()
  const titleId = useId()
  const mark = useMarkReviewed(page)
  if (!page.review_due) return null
  const days = space.review_interval_days
  return (
    <section
      aria-labelledby={titleId}
      className="mb-4 flex flex-col gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 sm:flex-row sm:items-start dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100"
    >
      <ClipboardCheck aria-hidden className="mt-0.5 hidden size-4 shrink-0 sm:block" />
      <div className="min-w-0 flex-1">
        <h3 id={titleId} className="font-medium">
          {t('wiki.review.due')}
        </h3>
        <p>
          {page.reviewed_at
            ? t('wiki.review.last', {
                date: formatDay(page.reviewed_at.slice(0, 10), i18n.language),
              })
            : t('wiki.review.never')}
          {days != null && <> {t('wiki.review.interval', { count: days })}</>}
        </p>
        {mark.error ? (
          <div className="mt-2">
            <WikiError error={mark.error} />
          </div>
        ) : null}
      </div>
      {abilities.edit && (
        <Button
          size="sm"
          variant="outline"
          className="self-start"
          disabled={mark.isPending}
          onClick={() => mark.mutate()}
        >
          {t('wiki.review.mark')}
        </Button>
      )}
    </section>
  )
}
