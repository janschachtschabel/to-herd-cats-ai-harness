import { Link2, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadMore } from '@/features/shared/states'
import type { TicketHit, WikiPage } from '@/lib/api'
import { errorMessage } from '@/lib/errors'
import { TicketRows } from '../TicketRows'
import { PickDialog } from './PickDialog'
import { useLinkPage, usePageTickets } from './queries'

/** "Linked tickets" under a page: the tickets linked to it that one may see. Whoever
 *  may edit the page is offered to link a ticket (found by key or title) and to unlink
 *  one; the server also asks for `ticket.edit` on the ticket and refuses otherwise. */
export function PageTickets({ page, editable }: { page: WikiPage; editable: boolean }) {
  const { t } = useTranslation()
  const tickets = usePageTickets(page.id)
  const link = useLinkPage()
  const [picking, setPicking] = useState(false)
  if (!editable && !tickets.isPending && !tickets.isError && tickets.items.length === 0) return null
  return (
    <section aria-labelledby="page-tickets" className="mt-8 flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h2 id="page-tickets" className="text-base font-semibold">
          {t('tickets.links.tickets')}
        </h2>
        {editable && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              link.reset()
              setPicking(true)
            }}
          >
            <Link2 aria-hidden />
            {t('tickets.links.addTicket')}
          </Button>
        )}
      </div>
      {tickets.isError ? (
        <ErrorState error={tickets.error} onRetry={() => void tickets.refetch()} />
      ) : tickets.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {tickets.isPending ? t('states.loading') : t('tickets.links.noTickets')}
        </p>
      ) : (
        <TicketRows
          tickets={tickets.items}
          action={
            editable
              ? (ticket) => (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={t('tickets.links.unlinkTicket', { key: ticket.key })}
                    title={t('tickets.links.unlinkTicket', { key: ticket.key })}
                    disabled={link.isPending}
                    onClick={() =>
                      link.mutate({ number: ticket.number, pageId: page.id, link: false })
                    }
                  >
                    <X aria-hidden />
                  </Button>
                )
              : undefined
          }
        />
      )}
      <LoadMore hasMore={tickets.hasMore} loading={tickets.loadingMore} onLoad={tickets.loadMore} />
      {link.error && !picking ? (
        <p role="alert" className="text-sm text-destructive">
          {errorMessage(t, link.error)}
        </p>
      ) : null}
      {editable && (
        <PickDialog
          error={picking ? link.error : undefined}
          type="ticket"
          open={picking}
          onOpenChange={(open) => {
            setPicking(open)
            if (!open) link.reset()
          }}
          title={t('tickets.links.addTicket')}
          onPick={(hit) =>
            link.mutate(
              { number: (hit as TicketHit).number, pageId: page.id, link: true },
              { onSuccess: () => setPicking(false) },
            )
          }
        />
      )}
    </section>
  )
}
