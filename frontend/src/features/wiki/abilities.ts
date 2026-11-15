import type { Me, Space, SpaceRole, WikiPage } from '@/lib/api'

/** What the person may do in a space's wiki. Decided only from the space's `my_role`
 *  and the system-wide `permissions` of `/auth/me` (CLAUDE.md rule 12); the server
 *  checks every action again. Mirrors `SPACE_ACTION_MIN_ROLE` in core/permissions.py. */
export interface WikiAbilities {
  create: boolean // page.create
  edit: boolean // page.edit: also see drafts, publish one's own
  publishAny: boolean // page.publish
  trash: boolean // page.trash
  moderate: boolean // page.moderate: the space's tags
  manage: boolean // space.manage: import, members, settings
  purge: boolean // page.purge (system-wide)
}

const RANK: Record<SpaceRole, number> = { viewer: 0, editor: 1, moderator: 2, admin: 3 }

export function wikiAbilities(space: Space, me: Me | null): WikiAbilities {
  const rank = space.my_role ? RANK[space.my_role] : -1
  return {
    create: rank >= RANK.editor,
    edit: rank >= RANK.editor,
    publishAny: rank >= RANK.moderator,
    trash: rank >= RANK.moderator,
    moderate: rank >= RANK.moderator,
    manage: rank >= RANK.admin,
    purge: me?.permissions.includes('page.purge') ?? false,
  }
}

/** A draft can be published by whoever may publish any, or by its author with page.edit. */
export function canPublish(abilities: WikiAbilities, page: WikiPage, me: Me | null): boolean {
  if (page.status !== 'draft') return false
  return abilities.publishAny || (abilities.edit && page.created_by.id === me?.user.id)
}
