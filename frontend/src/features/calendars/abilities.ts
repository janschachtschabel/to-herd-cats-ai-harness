import type { SpaceRole } from '@/lib/api'

/** What the person may do with a space's calendars, decided only from the space's
 *  `my_role` (CLAUDE.md rule 12); the server checks every action again. Mirrors
 *  `SPACE_ACTION_MIN_ROLE` in core/permissions.py (plan M10). */
export interface CalendarAbilities {
  read: boolean // calendar.read: see the calendars and their events
  write: boolean // calendar.write: create, change and delete events
  moderate: boolean // calendar.moderate: create, rename and archive calendars, import
}

const RANK: Record<SpaceRole, number> = { viewer: 0, editor: 1, moderator: 2, admin: 3 }

export function calendarAbilities(role: SpaceRole | null | undefined): CalendarAbilities {
  const rank = role ? RANK[role] : -1
  return {
    read: rank >= RANK.viewer,
    write: rank >= RANK.editor,
    moderate: rank >= RANK.moderator,
  }
}
