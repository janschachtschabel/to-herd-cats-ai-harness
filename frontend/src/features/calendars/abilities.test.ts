import { describe, expect, test } from 'vitest'
import { calendarAbilities } from './abilities'

describe('calendar abilities', () => {
  test('follow the space role alone', () => {
    expect(calendarAbilities(null)).toEqual({ read: false, write: false, moderate: false })
    expect(calendarAbilities('viewer')).toEqual({ read: true, write: false, moderate: false })
    expect(calendarAbilities('editor')).toEqual({ read: true, write: true, moderate: false })
    expect(calendarAbilities('moderator')).toEqual({ read: true, write: true, moderate: true })
    expect(calendarAbilities('admin')).toEqual({ read: true, write: true, moderate: true })
  })
})
