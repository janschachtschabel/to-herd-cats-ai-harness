import { Link } from '@tanstack/react-router'
import { Activity } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { navLinkActive, navLinkClass } from './navStyles'
import { SectionHeading } from './SectionHeading'

/** "With agents" (plan M6): my runs. Shown to people with AI or who manage agents. */
export function AgentsSection() {
  const { t } = useTranslation()
  return (
    <>
      <SectionHeading>{t('nav.agentWork')}</SectionHeading>
      <ul className="flex flex-col gap-0.5">
        <li>
          <Link to="/runs" className={navLinkClass} activeProps={navLinkActive}>
            <Activity className="size-4 shrink-0" aria-hidden />
            <span className="flex-1">{t('nav.myRuns')}</span>
          </Link>
        </li>
      </ul>
    </>
  )
}
