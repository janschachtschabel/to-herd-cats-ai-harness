import { describe, expect, test } from 'vitest'
import { listQuery, ticketSearch } from './filters'

describe('ticket list filters', () => {
  test('nothing chosen is "my tickets": assigned to me, not finished, newest change first', () => {
    expect(ticketSearch({})).toEqual({}) // toEqual ignores undefined keys
    expect(listQuery({})).toMatchObject({
      assignee: 'me',
      status_category: ['open', 'active', 'review'],
      sort: 'updated',
    })
  })

  test('everyone, every state, one category; invalid values are dropped', () => {
    expect(listQuery({ who: 'all', state: 'all' })).toMatchObject({
      assignee: undefined,
      status_category: undefined,
    })
    expect(listQuery({ state: 'done' }).status_category).toEqual(['done'])
    expect(
      ticketSearch({ who: 'x', state: 'gone', kind: 'saga', space: 'no-id', sort: 'name', q: ' ' }),
    ).toEqual({})
    const space = '00000000-0000-7000-8000-00000000000A'
    expect(ticketSearch({ space, kind: 'bug', q: ' Login ' })).toEqual({
      space: space.toLowerCase(),
      kind: 'bug',
      q: 'Login',
    })
  })
})
