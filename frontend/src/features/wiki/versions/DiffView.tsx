import { useTranslation } from 'react-i18next'
import { ErrorState, LoadingState } from '@/features/shared/states'
import { ApiError } from '@/lib/api'
import { WikiError } from '../WikiError'
import { DiffLines } from './DiffLines'
import { useDiff } from './queries'

/** The line diff of two versions; a too large diff (422) says so. */
export function DiffView({ pageId, from, to }: { pageId: string; from: number; to: number }) {
  const { t } = useTranslation()
  const diff = useDiff(pageId, { from, to })
  if (diff.isPending) return <LoadingState rows={3} />
  if (diff.isError) {
    return diff.error instanceof ApiError && diff.error.status === 422 ? (
      <WikiError error={diff.error} />
    ) : (
      <ErrorState error={diff.error} onRetry={() => void diff.refetch()} />
    )
  }
  const { data } = diff
  const changed = data.hunks.some((h) => h.kind !== 'equal')
  return (
    <section
      aria-label={t('wiki.versions.diffLabel', { from, to })}
      className="flex flex-col gap-2"
    >
      {data.title_changed && (
        <p className="text-sm">
          {t('wiki.versions.titleChanged', { from: data.from_title, to: data.to_title })}
        </p>
      )}
      {!changed ? (
        <p className="text-sm text-muted-foreground">{t('wiki.versions.noChanges')}</p>
      ) : (
        <DiffLines hunks={data.hunks} />
      )}
    </section>
  )
}
