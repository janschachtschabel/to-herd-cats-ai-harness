import { Link } from '@tanstack/react-router'
import { ArrowLeft, RotateCcw, Tag } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import type { VersionSummary, WikiPage } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { useWiki } from '../WikiContext'
import { WikiError } from '../WikiError'
import { DiffView } from './DiffView'
import { useRestoreVersion, useVersions } from './queries'
import { VersionLabelDialog } from './VersionLabelDialog'

/** The page's versions, newest first: who, how (source), when; the diff of two chosen
 *  versions; restoring one (as a new version) and naming one. The whole history needs
 *  page.edit (PageScreen shows it only then; review M2 R16). */
export function VersionsPanel({ page }: { page: WikiPage }) {
  const { t, i18n } = useTranslation()
  const { space, abilities } = useWiki()
  const versions = useVersions(page.id)
  const restore = useRestoreVersion(page)
  const [picked, setPicked] = useState<{ from?: number; to?: number }>({})
  const [restoring, setRestoring] = useState<VersionSummary | null>(null)
  const [labelling, setLabelling] = useState<VersionSummary | null>(null)
  const items = versions.items
  const to = picked.to ?? items[0]?.number
  const from = picked.from ?? items[1]?.number

  return (
    <section aria-labelledby="versions-heading" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="versions-heading" className="text-xl font-semibold tracking-tight">
          {t('wiki.versions.title', { title: page.title })}
        </h2>
        <Button variant="outline" asChild>
          <Link to="/spaces/$spaceId/p/$" params={{ spaceId: space.id, _splat: page.path }}>
            <ArrowLeft aria-hidden />
            {t('wiki.versions.back')}
          </Link>
        </Button>
      </div>
      {versions.isPending ? (
        <LoadingState />
      ) : versions.isError ? (
        <ErrorState error={versions.error} onRetry={() => void versions.refetch()} />
      ) : (
        <>
          <table className="w-full text-sm">
            <caption className="sr-only">{t('wiki.versions.caption')}</caption>
            <thead className="text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-1 pr-2 font-medium">{t('wiki.versions.from')}</th>
                <th className="py-1 pr-2 font-medium">{t('wiki.versions.to')}</th>
                <th className="py-1 pr-2 font-medium">{t('wiki.versions.version')}</th>
                <th className="py-1 pr-2 font-medium">{t('wiki.versions.who')}</th>
                <th className="py-1 font-medium">
                  <span className="sr-only">{t('wiki.versions.actions')}</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map((v) => (
                <tr key={v.number} className="align-top">
                  <td className="py-2 pr-2">
                    <input
                      type="radio"
                      name="diff-from"
                      className="accent-primary"
                      aria-label={t('wiki.versions.fromNamed', { number: v.number })}
                      checked={from === v.number}
                      onChange={() => setPicked((p) => ({ ...p, from: v.number }))}
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <input
                      type="radio"
                      name="diff-to"
                      className="accent-primary"
                      aria-label={t('wiki.versions.toNamed', { number: v.number })}
                      checked={to === v.number}
                      onChange={() => setPicked((p) => ({ ...p, to: v.number }))}
                    />
                  </td>
                  <td className="py-2 pr-2">
                    <div className="flex flex-wrap items-center gap-1.5 font-medium">
                      {t('wiki.versions.number', { number: v.number })}
                      {v.label && <Badge variant="secondary">{v.label}</Badge>}
                      <Badge variant="outline">{t(`wiki.versions.source.${v.source}`)}</Badge>
                    </div>
                    {v.change_summary && (
                      <p className="text-muted-foreground">{v.change_summary}</p>
                    )}
                  </td>
                  <td className="py-2 pr-2">
                    <div>{v.author.name ?? t('wiki.versions.unknownAuthor')}</div>
                    <div className="text-xs text-muted-foreground">
                      {formatDateTime(v.created_at, i18n.language)}
                    </div>
                  </td>
                  <td className="py-2">
                    {abilities.edit && (
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={t('wiki.versions.labelNamed', { number: v.number })}
                          onClick={() => setLabelling(v)}
                        >
                          <Tag aria-hidden />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={t('wiki.versions.restoreNamed', { number: v.number })}
                          onClick={() => setRestoring(v)}
                        >
                          <RotateCcw aria-hidden />
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <LoadMore
            hasMore={versions.hasMore}
            loading={versions.loadingMore}
            onLoad={versions.loadMore}
          />
          {from !== undefined && to !== undefined && from !== to ? (
            <DiffView pageId={page.id} from={from} to={to} />
          ) : (
            <p className="text-sm text-muted-foreground">{t('wiki.versions.pickTwo')}</p>
          )}
        </>
      )}
      {abilities.edit && (
        <>
          <ConfirmDialog
            open={restoring !== null}
            title={t('wiki.versions.restoreTitle')}
            text={t('wiki.versions.restoreText', { number: restoring?.number ?? 0 })}
            confirmLabel={t('wiki.versions.restore')}
            pending={restore.isPending}
            error={restore.error}
            errorView={<WikiError error={restore.error} />}
            onOpenChange={(open) => !open && setRestoring(null)}
            onConfirm={() =>
              restoring && restore.mutate(restoring.number, { onSuccess: () => setRestoring(null) })
            }
          />
          <VersionLabelDialog
            pageId={page.id}
            version={labelling}
            onClose={() => setLabelling(null)}
          />
        </>
      )}
    </section>
  )
}
