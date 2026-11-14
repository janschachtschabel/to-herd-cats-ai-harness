import type { Sprint } from '@/lib/api'
import type { TicketAbilities } from '../abilities'

/** The space's running sprint, if any (at most one, held by the database). */
export function activeSprint(sprints: Sprint[]): Sprint | undefined {
  return sprints.find((sprint) => sprint.state === 'active')
}

/** Where closing sends the unfinished tickets with `next`: the planned sprint that
 *  starts first (then by id), as the server picks it. */
export function nextPlanned(sprints: Sprint[]): Sprint | undefined {
  return sprints
    .filter((sprint) => sprint.state === 'planned')
    .sort((a, b) => a.starts_on.localeCompare(b.starts_on) || a.id.localeCompare(b.id))[0]
}

/** What a sprint offers its viewer: start (planned, nothing running), close (active);
 *  `blockedBy` names the running sprint that keeps a planned one from starting. */
export function sprintOffers(sprint: Sprint, sprints: Sprint[], abilities: TicketAbilities) {
  const running = activeSprint(sprints)
  const manage = abilities.manageSprints
  return {
    start: manage && sprint.state === 'planned' && !running,
    blockedBy: manage && sprint.state === 'planned' ? running : undefined,
    close: manage && sprint.state === 'active',
  }
}

/** The sprint to put tickets into unless one is chosen: the running one, else the
 *  planned one that starts first. */
export function defaultTarget(sprints: Sprint[]): Sprint | undefined {
  return activeSprint(sprints) ?? nextPlanned(sprints)
}
