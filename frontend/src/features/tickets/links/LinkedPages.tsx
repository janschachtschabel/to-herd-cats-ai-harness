import { Link } from '@tanstack/react-router'
import { FileText, Plus, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadMore } from '@/features/shared/states'
import type { SearchHit, Ticket } from '@/lib/api'
import { errorMessage } from '@/lib/errors'
import { PickDialog } from './PickDialog'
import { useLinkPage, useTicketPages } from './queries'

/** The wiki pages the ticket links (only those one sees); with `ticket.edit` a page
 *  can be found and linked, or a link removed. */
export function LinkedPages({ ticket, editable }: { ticket: Ticket; editable: boolean }) {
  const { t } = useTranslation()
  const pages = useTicketPages(ticket.number)
  const link = useLinkPage()
  const [picking, setPicking] = useState(false)
  return (
    <section aria-labelledby="ticket-pages" className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2">
        <h2 id="ticket-pages" className="text-xs font-medium text-muted-foreground">
          {t('tickets.links.pages')}
        </h2>
        {editable && (
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label={t('tickets.links.addPage')}
            title={t('tickets.links.addPage')}
            onClick={() => setPicking(true)}
          >
            <Plus aria-hidden />
          </Button>
        )}
      </div>
      {pages.isError ? (
        <ErrorState error={pages.error} onRetry={() => void pages.refetch()} />
      ) : pages.items.length === 0 ? (
        <span className="text-sm text-muted-foreground">
          {pages.isPending ? t('states.loading') : t('tickets.links.noPages')}
        </span>
      ) : (
        <ul className="flex flex-col gap-1">
          {pages.items.map((page) => (
            <li key={page.id} className="flex items-center gap-1.5 text-sm">
              <FileText className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
              <Link
                to="/spaces/$spaceId/p/$"
                params={{ spaceId: page.space_id, _splat: page.path }}
                className="min-w-0 flex-1 truncate hover:underline"
              >
                {page.title}
              </Link>
              {editable && (
                <Button
                  variant="ghost"
                  size="icon-xs"
                  aria-label={t('tickets.links.removePage', { title: page.title })}
                  disabled={link.isPending}
                  onClick={() =>
                    link.mutate({ number: ticket.number, pageId: page.id, link: false })
                  }
                >
                  <X aria-hidden />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={pages.hasMore} loading={pages.loadingMore} onLoad={pages.loadMore} />
      {link.error ? (
        <p role="alert" className="text-xs text-destructive">
          {errorMessage(t, link.error)}
        </p>
      ) : null}
      {editable && (
        <PickDialog
          type="page"
          open={picking}
          onOpenChange={setPicking}
          title={t('tickets.links.addPage')}
          onPick={(hit) =>
            link.mutate(
              { number: ticket.number, pageId: (hit as SearchHit).id, link: true },
              { onSuccess: () => setPicking(false) },
            )
          }
        />
      )}
    </section>
  )
}
