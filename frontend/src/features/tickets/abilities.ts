import type { SpaceRole } from '@/lib/api'

/** What the person may do with a space's tickets. Decided only from the space's
 *  `my_role` (CLAUDE.md rule 12); the server checks every action again. Mirrors
 *  `SPACE_ACTION_MIN_ROLE` in core/permissions.py (plan M4, decision 3). */
export interface TicketAbilities {
  read: boolean // ticket.read
  create: boolean // ticket.create
  edit: boolean // ticket.edit: also take an unassigned ticket, let go of one's own
  assign: boolean // ticket.assign: assign anyone who may read tickets here
  comment: boolean // channel.post: write in a ticket's thread (its `can_post` decides)
  manageStatuses: boolean // space.manage
}

const RANK: Record<SpaceRole, number> = { viewer: 0, editor: 1, moderator: 2, admin: 3 }

export function ticketAbilities(role: SpaceRole | null | undefined): TicketAbilities {
  const rank = role ? RANK[role] : -1
  return {
    read: rank >= RANK.viewer,
    create: rank >= RANK.editor,
    edit: rank >= RANK.editor,
    assign: rank >= RANK.moderator,
    comment: rank >= RANK.viewer,
    manageStatuses: rank >= RANK.admin,
  }
}

interface Assigned {
  assignee: { id: string } | null
}

/** "Take": an unassigned ticket, with `ticket.edit`. */
export function canTake(ticket: Assigned, abilities: TicketAbilities): boolean {
  return abilities.edit && ticket.assignee === null
}

/** "Let go": one's own assignment with `ticket.edit`; anyone's with `ticket.assign`. */
export function canRelease(
  ticket: Assigned,
  abilities: TicketAbilities,
  meId: string | undefined,
): boolean {
  if (ticket.assignee === null) return false
  return abilities.assign || (abilities.edit && ticket.assignee.id === meId)
}
