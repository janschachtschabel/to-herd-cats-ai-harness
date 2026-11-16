import { Link } from '@tanstack/react-router'
import {
  Bot,
  DatabaseBackup,
  Eye,
  History,
  LogIn,
  ScrollText,
  Search,
  Shield,
  Sparkles,
  Tags,
  UserRound,
  UsersRound,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { usePendingCount } from '@/features/admin/users/queries'
import { useMe } from '@/features/auth/queries'
import { useOpenSearch } from '@/features/search/SearchContext'
import { badgeCount } from '@/lib/format'
import { navLinkActive, navLinkClass } from './navStyles'
import { adminLinks, visibleSections, type AdminLink, type SectionId } from './nav'
import { SectionHeading } from './SectionHeading'
import { ActivitySection, ChannelsSection, DirectSection } from './SidebarMessaging'
import { AgentsSection } from './SidebarAgents'
import { SidebarSpaces } from './SidebarSpaces'
import { WorkSection } from './SidebarWork'

const ADMIN_ICONS: Record<AdminLink['to'], typeof UserRound> = {
  '/admin/users': UserRound,
  '/admin/sign-in': LogIn,
  '/admin/groups': UsersRound,
  '/admin/tags': Tags,
  '/admin/audit': History,
  '/admin/dm-inspect': Eye,
  '/admin/ai': Sparkles,
  '/admin/agents': Bot,
  '/admin/skills': ScrollText,
  '/admin/backup': DatabaseBackup,
}

/** The number of self-registered accounts awaiting approval, beside "Personen" (the
 *  link shows only with `user.manage`, so only such people ask). */
function PendingBadge() {
  const { t } = useTranslation()
  const count = usePendingCount(true)
  if (count === 0) return null
  return (
    <span className="ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-[11px] font-semibold text-primary-foreground tabular-nums">
      <span aria-hidden>{badgeCount(count)}</span>
      <span className="sr-only">{t('users.pending.navCount', { count })}</span>
    </span>
  )
}

function AdminSection() {
  const { t } = useTranslation()
  const links = adminLinks(useMe())
  return (
    <>
      <SectionHeading>
        <span className="inline-flex items-center gap-1.5">
          <Shield className="size-3.5" aria-hidden />
          {t('nav.admin')}
        </span>
      </SectionHeading>
      <ul className="flex flex-col gap-0.5">
        {links.map((link) => {
          const Icon = ADMIN_ICONS[link.to]
          return (
            <li key={link.to}>
              <Link to={link.to} className={navLinkClass} activeProps={navLinkActive}>
                <Icon className="size-4 shrink-0" aria-hidden />
                {t(link.labelKey)}
                {link.to === '/admin/users' && <PendingBadge />}
              </Link>
            </li>
          )
        })}
      </ul>
    </>
  )
}

function SpacesSection() {
  const { t } = useTranslation()
  return (
    <>
      <SectionHeading>
        <Link to="/spaces" className="rounded-sm hover:text-sidebar-foreground">
          {t('nav.spaces')}
        </Link>
      </SectionHeading>
      <SidebarSpaces />
    </>
  )
}

function SearchSection() {
  const { t } = useTranslation()
  const openSearch = useOpenSearch()
  return (
    <div className="pt-3">
      <button type="button" className={navLinkClass + ' w-full'} onClick={openSearch}>
        <Search className="size-4 shrink-0" aria-hidden />
        <span className="flex-1 text-left">{t('nav.search')}</span>
        <kbd className="rounded border border-sidebar-border px-1 text-[10px] text-sidebar-muted-foreground">
          {t('search.shortcut')}
        </kbd>
      </button>
    </div>
  )
}

// Sections of later milestones get their renderer when they arrive.
const SECTIONS: Partial<Record<SectionId, () => ReactNode>> = {
  activity: ActivitySection,
  search: SearchSection,
  channels: ChannelsSection,
  direct: DirectSection,
  spaces: SpacesSection,
  work: WorkSection,
  agents: AgentsSection,
  admin: AdminSection,
}

export function Sidebar() {
  const { t } = useTranslation()
  const sections = visibleSections(useMe())
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-sidebar-border px-4">
        <span aria-hidden className="inline-block size-2.5 rounded-full bg-sidebar-primary" />
        <span className="text-sm font-semibold tracking-tight">{t('app.name')}</span>
      </div>
      <nav aria-label={t('nav.label')} className="flex-1 overflow-y-auto px-2 pb-4">
        {sections.map((section) => {
          const Render = SECTIONS[section.id]
          return Render ? (
            <section key={section.id} data-section={section.id}>
              <Render />
            </section>
          ) : null
        })}
      </nav>
    </div>
  )
}
