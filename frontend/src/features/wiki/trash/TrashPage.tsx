import { useNavigate } from '@tanstack/react-router'
import { RotateCcw, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import type { TrashedPage } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { useWiki } from '../WikiContext'
import { WikiError } from '../WikiError'
import { usePurgePage, useRestorePage, useTrashList } from './queries'

/** Pages put into the trash (one row per batch: the page and what was below it). */
export function TrashPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { space, abilities } = useWiki()
  const list = useTrashList(space.id)
  const restore = useRestorePage(space.id)
  const purge = usePurgePage(space.id)
  const [purging, setPurging] = useState<TrashedPage | null>(null)

  if (!abilities.trash) return <EmptyState text={t('errors.forbidden')} />
  return (
    <section aria-labelledby="trash-heading" className="flex flex-col gap-4">
      <div>
        <h2 id="trash-heading" className="text-xl font-semibold tracking-tight">
          {t('wiki.trash.title')}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{t('wiki.trash.description')}</p>
      </div>
      <WikiError error={restore.error} />
      {list.isPending ? (
        <LoadingState />
      ) : list.isError ? (
        <ErrorState error={list.error} onRetry={() => void list.refetch()} />
      ) : list.items.length === 0 ? (
        <EmptyState text={t('wiki.trash.empty')} />
      ) : (
        <ul className="flex flex-col divide-y rounded-lg border">
          {list.items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{item.title}</p>
                <p className="text-xs text-muted-foreground">
                  {item.path} ·{' '}
                  {t('wiki.trash.trashedAt', {
                    when: formatDateTime(item.trashed_at, i18n.language),
                  })}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                disabled={restore.isPending}
                aria-label={t('wiki.trash.restoreNamed', { title: item.title })}
                onClick={() =>
                  restore.mutate(item.id, {
                    onSuccess: (page) =>
                      void navigate({
                        to: '/spaces/$spaceId/p/$',
                        params: { spaceId: space.id, _splat: page.path },
                      }),
                  })
                }
              >
                <RotateCcw aria-hidden />
                {t('wiki.trash.restore')}
              </Button>
              {abilities.purge && (
                <Button
                  variant="destructive"
                  size="sm"
                  aria-label={t('wiki.trash.purgeNamed', { title: item.title })}
                  onClick={() => setPurging(item)}
                >
                  <Trash2 aria-hidden />
                  {t('wiki.trash.purge')}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={list.hasMore} loading={list.loadingMore} onLoad={list.loadMore} />
      {abilities.purge && (
        <ConfirmDialog
          open={purging !== null}
          title={t('wiki.trash.purgeTitle')}
          text={t('wiki.trash.purgeText', { title: purging?.title ?? '' })}
          confirmLabel={t('wiki.trash.purge')}
          destructive
          pending={purge.isPending}
          error={purge.error}
          errorView={<WikiError error={purge.error} />}
          onOpenChange={(open) => !open && setPurging(null)}
          onConfirm={() =>
            purging && purge.mutate(purging.id, { onSuccess: () => setPurging(null) })
          }
        />
      )}
    </section>
  )
}
