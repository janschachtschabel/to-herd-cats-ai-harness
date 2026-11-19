/** The actions the backend writes (Task 8), for the filter and their labels. */
export const AUDIT_ACTIONS = [
  'user.created',
  'user.updated',
  'user.password_changed',
  'user.signed_out',
  'user.session_ended',
  'user.deactivated',
  'user.reactivated',
  'group.created',
  'group.updated',
  'group.deleted',
  'group.member_added',
  'group.member_removed',
  'space.created',
  'space.updated',
  'space.member_set',
  'space.member_removed',
  'space.admin_access',
  'dm.admin_lookup',
  'dm.admin_access',
  'message.moderated',
] as const

/** How names and values of details are shown; the identity by default. */
export interface DetailWords {
  key: (key: string) => string
  value: (key: string, value: string) => string
}

const AS_IS: DetailWords = { key: (key) => key, value: (_key, value) => value }

function show(key: string, value: unknown, words: DetailWords): string {
  if (value === null || value === undefined) return '–'
  return typeof value === 'object' ? JSON.stringify(value) : words.value(key, String(value))
}

/** An entry's details as one short line, e.g. `name: A → B, role: editor`. Ids of
 *  members are left out; they say nothing to a reader. */
export function summarizeDetails(
  details: Record<string, unknown> | null | undefined,
  words: DetailWords = AS_IS,
): string {
  if (!details) return ''
  const parts: string[] = []
  for (const [key, value] of Object.entries(details)) {
    if (key === 'member_id') continue
    if (key === 'changes' && value && typeof value === 'object') {
      for (const [field, change] of Object.entries(value as Record<string, unknown>)) {
        const { from, to } = (change ?? {}) as { from?: unknown; to?: unknown }
        parts.push(`${words.key(field)}: ${show(field, from, words)} → ${show(field, to, words)}`)
      }
      continue
    }
    parts.push(`${words.key(key)}: ${show(key, value, words)}`)
  }
  return parts.join(', ')
}
