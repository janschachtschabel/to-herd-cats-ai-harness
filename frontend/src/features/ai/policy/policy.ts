import type { Schemas } from '@/lib/api'
import { DATA_LOCATIONS } from '../display'

type SpaceUpdate = Schemas['SpaceUpdateIn']

/**
 * The space settings body with its AI part: the policy, and the allowed locations only
 * for `restricted` (the backend refuses them with any other policy). Whoever manages
 * the space sets it, with or without AI of their own (governance, not use).
 */
export function withAiPolicy(values: SpaceUpdate): SpaceUpdate {
  const { ai_policy, allowed_locations, ...rest } = values
  if (!ai_policy) return rest
  if (ai_policy !== 'restricted') return { ...rest, ai_policy }
  const chosen = new Set(allowed_locations ?? [])
  return { ...rest, ai_policy, allowed_locations: DATA_LOCATIONS.filter((l) => chosen.has(l)) }
}

/** Restricted without any location would leave AI nothing: say so before saving. */
export function missingLocations(values: SpaceUpdate): boolean {
  return values.ai_policy === 'restricted' && (values.allowed_locations ?? []).length === 0
}
