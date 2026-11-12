import type { Space, SpaceKind, SpaceRole } from '@/lib/api'

export const SPACE_ROLES: readonly SpaceRole[] = ['viewer', 'editor', 'moderator', 'admin']

export const KIND_ORDER: readonly SpaceKind[] = ['open', 'team', 'personal']

/** Whether this is the person's own personal space ("Mein Bereich"). */
export function isOwnPersonal(space: Space, meId: string | undefined): boolean {
  return space.kind === 'personal' && space.owner_user_id === meId
}

/** Spaces by kind, in the order open, team, personal; one's own personal space first in
 *  its group, the rest by name. Kinds without spaces are left out. */
export function groupByKind(
  spaces: readonly Space[],
  meId: string | undefined,
): { kind: SpaceKind; spaces: Space[] }[] {
  return KIND_ORDER.map((kind) => ({
    kind,
    spaces: spaces
      .filter((space) => space.kind === kind)
      .sort(
        (a, b) =>
          Number(isOwnPersonal(b, meId)) - Number(isOwnPersonal(a, meId)) ||
          a.name.localeCompare(b.name),
      ),
  })).filter((group) => group.spaces.length > 0)
}

/** What the sidebar lists: open and team spaces, then one's own personal space. Other
 *  people's personal spaces (visible to admins) stay on the spaces page. */
export function sidebarSpaces(spaces: readonly Space[], meId: string | undefined): Space[] {
  return groupByKind(spaces, meId)
    .flatMap((group) => group.spaces)
    .filter((space) => space.kind !== 'personal' || isOwnPersonal(space, meId))
}

/** Whether the members of a space can be changed by someone holding `my_role`. */
export function canEditMembers(space: Space): boolean {
  return space.my_role === 'admin' && space.kind !== 'personal'
}

/** Whether name, description and icon can be changed. */
export function canEditSettings(space: Space): boolean {
  return space.my_role === 'admin'
}
