import type { Schemas } from '@/lib/api'
import { DATA_LOCATIONS } from '../display'

type SpaceUpdate = Schemas['SpaceUpdateIn']

/**
 * The space settings body with its AI part: left out entirely where the person does
 * not see AI settings; otherwise the policy, and the allowed locations only for
 * `restricted` (the backend refuses them with any other policy).
 */
export function withAiPolicy(values: SpaceUpdate, shown: boolean): SpaceUpdate {
  const { ai_policy, allowed_locations, ...rest } = values
  if (!shown || !ai_policy) return rest
  if (ai_policy !== 'restricted') return { ...rest, ai_policy }
  const chosen = new Set(allowed_locations ?? [])
  return { ...rest, ai_policy, allowed_locations: DATA_LOCATIONS.filter((l) => chosen.has(l)) }
}

/** Restricted without any location would leave AI nothing: say so before saving. */
export function missingLocations(values: SpaceUpdate, shown: boolean): boolean {
  return shown && values.ai_policy === 'restricted' && (values.allowed_locations ?? []).length === 0
}
