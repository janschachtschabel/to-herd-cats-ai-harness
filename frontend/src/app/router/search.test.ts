import { describe, expect, it } from 'vitest'

import { runSearch } from './aiRoutes'
import {
  messageSearch,
  oauthDoneSearch,
  pageSearch,
  profileSearch,
  serverSearch,
  skillsSearch,
  usersSearch,
} from './search'

/** TanStack Router lays `validateSearch`'s result over the raw search: a key the
 *  validator leaves out keeps its raw, unchecked value. */
function seen<T extends object>(
  validate: (s: Record<string, unknown>) => T,
  raw: Record<string, unknown>,
) {
  return { ...raw, ...validate(raw) } as Record<string, unknown>
}

const HOSTILE = '<img src=x onerror=alert(1)>'

describe('validateSearch keeps no unchecked value', () => {
  it.each([
    ['messages', messageSearch, ['thread', 'message']],
    ['pages', pageSearch, ['thread', 'message', 'view', 'discussion']],
    ['skills', skillsSearch, ['view']],
    ['users', usersSearch, ['filter']],
    ['servers', serverSearch, ['read']],
    ['runs', runSearch, ['state', 'stop_reason']],
    ['profile', profileSearch, ['linked', 'link_error']],
  ] as const)('%s', (_name, validate, keys) => {
    const raw = Object.fromEntries(keys.map((key) => [key, HOSTILE]))
    const result = seen(validate as (s: Record<string, unknown>) => object, raw)
    for (const key of keys) expect(result[key], key).toBeUndefined()
  })

  it('oauth done falls back to failed', () => {
    expect(seen(oauthDoneSearch, { status: HOSTILE }).status).toBe('failed')
  })

  it('valid values still pass', () => {
    const id = '0f8fad5b-d9cb-469f-a165-70867728950e'
    expect(seen(messageSearch, { thread: id.toUpperCase() }).thread).toBe(id)
    expect(seen(pageSearch, { view: 'live', discussion: 'true' })).toMatchObject({
      view: 'live',
      discussion: true,
    })
    expect(seen(skillsSearch, { view: 'proposals' }).view).toBe('proposals')
    expect(seen(serverSearch, { read: 'ok' }).read).toBe('ok')
    expect(seen(runSearch, { state: 'running' }).state).toBe('running')
  })
})
