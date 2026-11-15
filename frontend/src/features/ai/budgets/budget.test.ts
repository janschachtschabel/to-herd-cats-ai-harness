import { describe, expect, test } from 'vitest'
import { limitInput, parseLimits, type Budget } from './budget'

describe('budget limits as typed', () => {
  test('take whole tokens and euros with up to two decimals, either mark', () => {
    expect(parseLimits({ tokens: ' 1000 ', cost: '' })).toEqual({
      ok: true,
      tokens_per_day: 1000,
      cost_per_day: null,
    })
    expect(parseLimits({ tokens: '', cost: '2,5' })).toEqual({
      ok: true,
      tokens_per_day: null,
      cost_per_day: '2.5',
    })
    expect(parseLimits({ tokens: '1', cost: '1000000000' }).ok).toBe(true)
  })

  test('refuse zero, fractions, grouping, too much and nothing at all', () => {
    const errors = (tokens: string, cost: string) => {
      const result = parseLimits({ tokens, cost })
      return result.ok ? null : result.errors
    }
    expect(errors('0', '')).toEqual({ tokens: true })
    expect(errors('1.5', '')).toEqual({ tokens: true })
    expect(errors(String(10 ** 12 + 1), '')).toEqual({ tokens: true })
    expect(errors('', '0')).toEqual({ cost: true })
    expect(errors('', '1.000')).toEqual({ cost: true })
    expect(errors('', '1000000000.01')).toEqual({ cost: true })
    expect(errors('', '')).toEqual({ missing: true })
  })

  test('a stored budget fills the form in the reader’s locale', () => {
    const budget = { tokens_per_day: 50000, cost_per_day: '5.00' } as Budget
    expect(limitInput(budget, 'de')).toEqual({ tokens: '50000', cost: '5,00' })
    expect(limitInput(budget, 'en')).toEqual({ tokens: '50000', cost: '5.00' })
    expect(limitInput(undefined, 'de')).toEqual({ tokens: '', cost: '' })
  })
})
