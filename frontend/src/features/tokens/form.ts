import type { Schemas } from '@/lib/api'
import { DEFAULT_EXPIRY_DAYS } from './display'

/** The token form: the body's fields, with the spaces as a choice between all of the
 *  owner's and a list (an empty list is refused by the body's schema). */
export interface TokenValues {
  name: string
  mode: Schemas['TokenMode']
  scope: 'all' | 'chosen'
  space_ids: string[]
  expires_in_days: number
}

export const EMPTY_TOKEN: TokenValues = {
  name: '',
  mode: 'read',
  scope: 'all',
  space_ids: [],
  expires_in_days: DEFAULT_EXPIRY_DAYS,
}

export function tokenBody(values: TokenValues): Schemas['TokenIn'] {
  return {
    name: values.name.trim(),
    mode: values.mode,
    expires_in_days: values.expires_in_days,
    space_ids: values.scope === 'all' ? null : values.space_ids,
  }
}
