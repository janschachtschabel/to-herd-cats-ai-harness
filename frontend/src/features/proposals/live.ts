import type { LiveEvent } from '@/lib/live'
import { proposalKeys } from './queries'

/** `proposal.changed` (made, accepted, rejected, withdrawn) carries the space and the
 *  proposal: their lists and the proposal refetch through the API. An accepted change
 *  also writes a page; its viewers learn that from the page itself. */
export function proposalEventKeys(event: LiveEvent): (readonly unknown[])[] {
  const keys: (readonly unknown[])[] = []
  if (event.spaceId) keys.push(proposalKeys.space(event.spaceId))
  if (event.proposalId) keys.push(proposalKeys.detail(event.proposalId))
  return keys
}
