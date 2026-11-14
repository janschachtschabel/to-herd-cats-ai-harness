import { useTranslation } from 'react-i18next'
import { useWiki } from '../WikiContext'

/** Narrows the tree to the pages whose review is due; shown while the space has a
 *  review interval (or the filter is on). */
export function TreeReviewFilter() {
  const { t } = useTranslation()
  const { space, reviewFilter, filterByReview } = useWiki()
  if (space.review_interval_days == null && !reviewFilter) return null
  return (
    <label className="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
      <input
        type="checkbox"
        className="size-4 accent-primary"
        checked={reviewFilter}
        onChange={(event) => filterByReview(event.target.checked)}
      />
      {t('wiki.review.filter')}
    </label>
  )
}
