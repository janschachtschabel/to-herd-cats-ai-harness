import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { useMe } from '@/features/auth/queries'
import { DiscussionPanel } from '@/features/messaging/discussion/DiscussionPanel'
import { useSpace } from '@/features/spaces/queries'
import type { Ticket } from '@/lib/api'
import { ticketAbilities } from './abilities'
import { KindLabel } from './parts'
import { useTicketThread } from './queries'
import { TicketChildren } from './TicketChildren'
import { TicketDescription, TicketTitle } from './TicketText'
import { TicketFields } from './TicketFields'

/** A ticket: title and description (Markdown), its fields on the right, its children,
 *  and below its discussion with the grey timeline. What one may change comes from the
 *  space's `my_role` only; until the space is known, nothing is offered. */
export function TicketView({
  ticket,
  thread,
  message,
}: {
  ticket: Ticket
  thread?: string
  message?: string
}) {
  const { t } = useTranslation()
  const me = useMe()
  const space = useSpace(ticket.space_id)
  const role = space.data?.my_role
  const abilities = ticketAbilities(role)
  const conversation = useTicketThread(ticket.number)

  return (
    <article aria-labelledby="ticket-title" className="flex flex-col gap-6">
      <div>
        <nav
          aria-label={t('tickets.view.breadcrumbs')}
          className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
        >
          <Link to="/tickets" className="hover:underline">
            {t('tickets.title')}
          </Link>
          <span aria-hidden>/</span>
          {space.data && (
            <>
              <Link
                to="/spaces/$spaceId"
                params={{ spaceId: space.data.id }}
                className="hover:underline"
              >
                {space.data.name}
              </Link>
              <span aria-hidden>/</span>
            </>
          )}
          <span className="font-mono">{ticket.key}</span>
          <KindLabel kind={ticket.kind} />
        </nav>
        <TicketTitle ticket={ticket} editable={abilities.edit} />
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="flex min-w-0 flex-col gap-6">
          <TicketDescription ticket={ticket} editable={abilities.edit} />
          <TicketChildren ticket={ticket} />
        </div>
        <TicketFields ticket={ticket} abilities={abilities} meId={me?.user.id} />
      </div>
      <DiscussionPanel
        conversation={conversation}
        spaceRole={role}
        title={t('tickets.discussion.title')}
        emptyText={t('tickets.discussion.empty')}
        composerLabel={t('tickets.discussion.composer')}
        thread={thread}
        highlight={message}
        className="h-[70dvh]"
      />
    </article>
  )
}
