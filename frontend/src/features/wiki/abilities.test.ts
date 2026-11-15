import { describe, expect, test } from 'vitest'
import type { WikiPage } from '@/lib/api'
import { makeMe, makeSpace } from '@/test/api'
import { canPublish, wikiAbilities } from './abilities'

describe('wikiAbilities', () => {
  const me = makeMe([])

  test('from the space role alone', () => {
    expect(wikiAbilities(makeSpace({ my_role: 'viewer' }), me)).toMatchObject({
      create: false,
      edit: false,
      publishAny: false,
      trash: false,
      manage: false,
    })
    expect(wikiAbilities(makeSpace({ my_role: 'editor' }), me)).toMatchObject({
      create: true,
      edit: true,
      publishAny: false,
      trash: false,
    })
    expect(wikiAbilities(makeSpace({ my_role: 'moderator' }), me)).toMatchObject({
      publishAny: true,
      trash: true,
      moderate: true,
      manage: false,
    })
    expect(wikiAbilities(makeSpace({ my_role: 'admin' }), me).manage).toBe(true)
    expect(wikiAbilities(makeSpace({ my_role: null }), me).create).toBe(false)
  })

  test('purging needs the system right', () => {
    const space = makeSpace({ my_role: 'admin' })
    expect(wikiAbilities(space, me).purge).toBe(false)
    expect(wikiAbilities(space, makeMe(['page.purge'])).purge).toBe(true)
  })

  test('an editor publishes own drafts only', () => {
    const editor = wikiAbilities(makeSpace({ my_role: 'editor' }), me)
    const draft = {
      status: 'draft',
      created_by: { type: 'user', id: me.user.id },
    } as WikiPage
    expect(canPublish(editor, draft, me)).toBe(true)
    expect(canPublish(editor, { ...draft, created_by: { type: 'user', id: 'x' } }, me)).toBe(false)
    expect(canPublish(editor, { ...draft, status: 'published' }, me)).toBe(false)
    const moderator = wikiAbilities(makeSpace({ my_role: 'moderator' }), me)
    expect(canPublish(moderator, { ...draft, created_by: { type: 'user', id: 'x' } }, me)).toBe(
      true,
    )
  })
})
