import { Link } from '@tanstack/react-router'
import {
  BookOpen,
  CalendarClock,
  Inbox,
  Layers,
  ScrollText,
  SquareKanban,
  Timer,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { automationAbilities } from '@/features/automations/abilities'
import { ProposalsTab } from '@/features/proposals/ProposalsTab'
import { skillAbilities } from '@/features/skills/abilities'
import { ticketAbilities } from '@/features/tickets/abilities'
import type { Me, Space } from '@/lib/api'
import { cn } from '@/lib/utils'
import { wikiAbilities } from './abilities'

export type SpaceView =
  'wiki' | 'proposals' | 'board' | 'epics' | 'sprints' | 'backlog' | 'skills' | 'automations'

const tab =
  'inline-flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none'

/** The views of a space: its wiki (pages, trash, settings), its proposals for page
 *  editors (with the number of open ones), with `ticket.read` its board, its epics, its sprints and its backlog, and its skills for those who may
 *  read them (AI and a role in the space, or `skill.manage`), and its automations
 *  for people with AI and a role here (or `agent.manage`). */
export function SpaceTabs({
  space,
  me,
  current,
}: {
  space: Space
  me: Me | null
  current: SpaceView
}) {
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
      {wikiAbilities(space, me).edit && (
        <ProposalsTab space={space} linkProps={look('proposals')} />
      )}
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
      {skillAbilities(me, space).read && (
        <Link to="/spaces/$spaceId/skills" params={params} {...look('skills')}>
          <ScrollText className="size-4" aria-hidden />
          {t('skills.tab')}
        </Link>
      )}
      {automationAbilities(me, space).list && (
        <Link to="/spaces/$spaceId/automations" params={params} {...look('automations')}>
          <CalendarClock className="size-4" aria-hidden />
          {t('automations.space.tab')}
        </Link>
      )}
    </nav>
  )
}
