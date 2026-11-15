import { Link } from '@tanstack/react-router'
import { Activity, Bot, CalendarClock, Plug, ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { usesAi } from '@/features/ai/display'
import { usePendingApprovalCount } from '@/features/approvals/queries'
import { useMe } from '@/features/auth/queries'
import { navLinkActive, navLinkClass } from './navStyles'
import { SectionHeading } from './SectionHeading'

/** The releases waiting for me, with their count (only people with AI are asked). */
function ApprovalsLink() {
  const { t } = useTranslation()
  const { count, more } = usePendingApprovalCount(true)
  return (
    <Link to="/approvals" className={navLinkClass} activeProps={navLinkActive}>
      <ShieldCheck className="size-4 shrink-0" aria-hidden />
      <span className="flex-1">{t('nav.approvals')}</span>
      {count > 0 && (
        <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-violet-600 px-1.5 text-[11px] font-semibold text-white tabular-nums">
          <span aria-hidden>{more ? `${count}+` : count}</span>
          <span className="sr-only">{t('nav.approvalsCount', { count })}</span>
        </span>
      )}
    </Link>
  )
}

/** "With agents" (plan M6, M7, M8): releases waiting for me, my runs, my own agents,
 *  my automations, my connections to external servers. Shown to
 *  people with AI or who manage agents. */
export function AgentsSection() {
  const { t } = useTranslation()
  const me = useMe()
  return (
    <>
      <SectionHeading>{t('nav.agentWork')}</SectionHeading>
      <ul className="flex flex-col gap-0.5">
        {usesAi(me) && (
          <li>
            <ApprovalsLink />
          </li>
        )}
        <li>
          <Link to="/runs" className={navLinkClass} activeProps={navLinkActive}>
            <Activity className="size-4 shrink-0" aria-hidden />
            <span className="flex-1">{t('nav.myRuns')}</span>
          </Link>
        </li>
        {usesAi(me) && (
          <li>
            <Link to="/my-agents" className={navLinkClass} activeProps={navLinkActive}>
              <Bot className="size-4 shrink-0" aria-hidden />
              <span className="flex-1">{t('nav.myAgents')}</span>
            </Link>
          </li>
        )}
        {usesAi(me) && (
          <li>
            <Link to="/automations" className={navLinkClass} activeProps={navLinkActive}>
              <CalendarClock className="size-4 shrink-0" aria-hidden />
              <span className="flex-1">{t('nav.myAutomations')}</span>
            </Link>
          </li>
        )}
        {usesAi(me) && (
          <li>
            <Link to="/my-connections" className={navLinkClass} activeProps={navLinkActive}>
              <Plug className="size-4 shrink-0" aria-hidden />
              <span className="flex-1">{t('nav.myConnections')}</span>
            </Link>
          </li>
        )}
      </ul>
    </>
  )
}
