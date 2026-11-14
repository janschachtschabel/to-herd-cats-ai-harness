import { useTranslation } from 'react-i18next'
import { LoadingState } from '@/features/shared/states'
import { DiffView } from '@/features/wiki/versions/DiffView'
import { useVersions } from '@/features/wiki/versions/queries'

/** What changed on the page since the proposal was made: the diff from its base
 *  version to the newest one. Changes a live session folded into the base version
 *  itself show only in the merge below. */
export function PageChanges({
  pageId,
  baseVersion,
}: {
  pageId: string
  baseVersion: number | null
}) {
  const { t } = useTranslation()
  const versions = useVersions(pageId)
  const newest = versions.items[0]?.number
  return (
    <section aria-labelledby="page-changes" className="flex flex-col gap-2">
      <h3 id="page-changes" className="text-sm font-medium">
        {t('proposals.merge.meanwhile')}
      </h3>
      {versions.isPending ? (
        <LoadingState rows={2} />
      ) : baseVersion === null || newest === undefined || newest <= baseVersion ? (
        <p className="text-sm text-muted-foreground">{t('proposals.merge.sameVersion')}</p>
      ) : (
        <DiffView pageId={pageId} from={baseVersion} to={newest} />
      )}
    </section>
  )
}
