import { Link } from '@tanstack/react-router'
import { BookOpen, Inbox, Layers, SquareKanban, Timer } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { ticketAbilities } from '@/features/tickets/abilities'
import type { Space } from '@/lib/api'
import { cn } from '@/lib/utils'

export type SpaceView = 'wiki' | 'board' | 'epics' | 'sprints' | 'backlog'

const tab =
  'inline-flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none'

/** The views of a space: its wiki (pages, trash, settings), and with `ticket.read`
 *  its board, its epics, its sprints and its backlog. */
export function SpaceTabs({ space, current }: { space: Space; current: SpaceView }) {
  const { t } = useTranslation()
  const params = { spaceId: space.id }
  // The router marks a link current by itself (the wiki's on every space address);
  // here the view decides, so only exact addresses count for the router.
  const look = (view: SpaceView) => ({
    activeOptions: { exact: true },
    'aria-current': current === view ? ('page' as const) : undefined,
    className: cn(
      tab,
      current === view
        ? 'border-primary font-medium text-foreground'
        : 'border-transparent text-muted-foreground hover:text-foreground',
    ),
  })
  return (
    <nav aria-label={t('tickets.space.views')} className="mb-4 flex gap-1 overflow-x-auto border-b">
      <Link to="/spaces/$spaceId" params={params} {...look('wiki')}>
        <BookOpen className="size-4" aria-hidden />
        {t('tickets.space.wiki')}
      </Link>
      {ticketAbilities(space.my_role).read && (
        <>
          <Link to="/spaces/$spaceId/board" params={params} {...look('board')}>
            <SquareKanban className="size-4" aria-hidden />
            {t('tickets.space.board')}
          </Link>
          <Link to="/spaces/$spaceId/epics" params={params} {...look('epics')}>
            <Layers className="size-4" aria-hidden />
            {t('tickets.space.epics')}
          </Link>
          <Link to="/spaces/$spaceId/sprints" params={params} {...look('sprints')}>
            <Timer className="size-4" aria-hidden />
            {t('tickets.space.sprints')}
          </Link>
          <Link to="/spaces/$spaceId/backlog" params={params} {...look('backlog')}>
            <Inbox className="size-4" aria-hidden />
            {t('tickets.space.backlog')}
          </Link>
        </>
      )}
    </nav>
  )
}
