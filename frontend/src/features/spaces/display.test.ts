import { describe, expect, test } from 'vitest'
import { makeSpace } from '@/test/api'
import { canEditMembers, canEditSettings, groupByKind, sidebarSpaces } from './display'

const ME = 'me'
const mine = makeSpace({ kind: 'personal', name: 'Zora', owner_user_id: ME })
const other = makeSpace({ kind: 'personal', name: 'Anna', owner_user_id: 'other' })
const open = makeSpace({ kind: 'open', name: 'Handbuch' })
const teamB = makeSpace({ kind: 'team', name: 'Beta' })
const teamA = makeSpace({ kind: 'team', name: 'Alpha' })

describe('space display rules', () => {
  test('groups by kind in a fixed order, own personal space first', () => {
    const groups = groupByKind([other, teamB, mine, open, teamA], ME)
    expect(groups.map((g) => [g.kind, g.spaces.map((s) => s.name)])).toEqual([
      ['open', ['Handbuch']],
      ['team', ['Alpha', 'Beta']],
      ['personal', ['Zora', 'Anna']],
    ])
    expect(groupByKind([teamA], ME).map((g) => g.kind)).toEqual(['team'])
  })

  test("the sidebar leaves out other people's personal spaces", () => {
    expect(sidebarSpaces([other, teamB, mine, open], ME).map((s) => s.name)).toEqual([
      'Handbuch',
      'Beta',
      'Zora',
    ])
  })

  test('only a space admin edits; members of personal spaces are fixed', () => {
    expect(canEditMembers(makeSpace({ my_role: 'admin' }))).toBe(true)
    expect(canEditMembers(makeSpace({ my_role: 'moderator' }))).toBe(false)
    expect(canEditMembers({ ...mine, my_role: 'admin' })).toBe(false)
    expect(canEditSettings({ ...mine, my_role: 'admin' })).toBe(true)
    expect(canEditSettings(makeSpace({ my_role: null }))).toBe(false)
  })
})
