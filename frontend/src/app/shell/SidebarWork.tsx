import { Link } from '@tanstack/react-router'
import { LayoutDashboard, SquareKanban } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useTicketCount } from '@/features/tickets/queries'
import { badgeCount } from '@/lib/format'
import { navLinkActive, navLinkClass } from './navStyles'
import { SectionHeading } from './SectionHeading'

/** "Work" (spec 6.2): the tickets, with how many unfinished ones are mine, and my
 *  board across spaces (plan M4b). */
export function WorkSection() {
  const { t } = useTranslation()
  const count = useTicketCount()
  return (
    <>
      <SectionHeading>{t('nav.work')}</SectionHeading>
      <ul className="flex flex-col gap-0.5">
        <li>
          <Link to="/tickets" className={navLinkClass} activeProps={navLinkActive}>
            <SquareKanban className="size-4 shrink-0" aria-hidden />
            <span className="flex-1">{t('nav.tickets')}</span>
            {count > 0 && (
              <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-sidebar-primary px-1.5 text-[11px] font-semibold text-sidebar-primary-foreground tabular-nums">
                <span aria-hidden>{badgeCount(count)}</span>
                <span className="sr-only">{t('tickets.sidebar.count', { count })}</span>
              </span>
            )}
          </Link>
        </li>
        <li>
          <Link to="/my-board" className={navLinkClass} activeProps={navLinkActive}>
            <LayoutDashboard className="size-4 shrink-0" aria-hidden />
            <span className="flex-1">{t('nav.myBoard')}</span>
          </Link>
        </li>
      </ul>
    </>
  )
}
