import type { Me, Permission } from '@/lib/api'

/** The milestone this build is at; sections of later milestones stay hidden. */
export const CURRENT_MILESTONE = 2

export type SectionId = 'activity' | 'search' | 'channels' | 'direct' | 'spaces' | 'work' | 'admin'

export interface NavSection {
  id: SectionId
  /** The milestone that brings the section (spec section 14). */
  milestone: number
  /** Shown only to people holding at least one of these rights. */
  anyOf?: Permission[]
}

/** The sidebar of spec 6.2, top to bottom, plus the administration for admins. */
export const NAV_SECTIONS: readonly NavSection[] = [
  { id: 'activity', milestone: 3 },
  { id: 'search', milestone: 2 },
  { id: 'channels', milestone: 3 },
  { id: 'direct', milestone: 3 },
  { id: 'spaces', milestone: 1 },
  { id: 'work', milestone: 4 },
  { id: 'admin', milestone: 1, anyOf: ['user.manage', 'group.manage', 'audit.read'] },
]

export interface AdminLink {
  to: '/admin/users' | '/admin/groups' | '/admin/audit'
  labelKey: 'nav.users' | 'nav.groups' | 'nav.audit'
  permission: Permission
}

export const ADMIN_LINKS: readonly AdminLink[] = [
  { to: '/admin/users', labelKey: 'nav.users', permission: 'user.manage' },
  { to: '/admin/groups', labelKey: 'nav.groups', permission: 'group.manage' },
  { to: '/admin/audit', labelKey: 'nav.audit', permission: 'audit.read' },
]

function holds(me: Me | null, permission: Permission): boolean {
  return me?.permissions.includes(permission) ?? false
}

/** The sections `me` sees at `milestone`. */
export function visibleSections(
  me: Me | null,
  milestone: number = CURRENT_MILESTONE,
): NavSection[] {
  return NAV_SECTIONS.filter(
    (section) =>
      section.milestone <= milestone &&
      (!section.anyOf || section.anyOf.some((permission) => holds(me, permission))),
  )
}

/** The administration pages `me` may open. */
export function adminLinks(me: Me | null): AdminLink[] {
  return ADMIN_LINKS.filter((link) => holds(me, link.permission))
}
