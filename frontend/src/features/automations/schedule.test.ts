import { describe, expect, test } from 'vitest'
import { cronOf, DEFAULT_PRESET, presetOf, type Preset } from './schedule'

const preset = (overrides: Partial<Preset>): Preset => ({ ...DEFAULT_PRESET, ...overrides })

describe('cron presets', () => {
  test('each preset writes its cron', () => {
    expect(cronOf(preset({ kind: 'hourly', minute: 15 }))).toBe('15 * * * *')
    expect(cronOf(preset({ kind: 'daily', time: '07:30' }))).toBe('30 7 * * *')
    expect(cronOf(preset({ kind: 'weekdays', time: '09:05' }))).toBe('5 9 * * 1-5')
    expect(cronOf(preset({ kind: 'weekly', time: '16:00', weekday: 5 }))).toBe('0 16 * * 5')
    expect(cronOf(preset({ kind: 'weekly', time: '10:00', weekday: 7 }))).toBe('0 10 * * 0')
    expect(cronOf(preset({ kind: 'monthly', time: '08:00', monthDay: 1 }))).toBe('0 8 1 * *')
    expect(cronOf(preset({ kind: 'custom', cron: ' */30 8-18 * * 1-5 ' }))).toBe(
      '*/30 8-18 * * 1-5',
    )
  })

  test('an unfinished field gives no cron yet', () => {
    expect(cronOf(preset({ kind: 'daily', time: '' }))).toBeNull()
    expect(cronOf(preset({ kind: 'daily', time: '25:00' }))).toBeNull()
    expect(cronOf(preset({ kind: 'hourly', minute: 60 }))).toBeNull()
    expect(cronOf(preset({ kind: 'monthly', monthDay: 31 }))).toBeNull()
    expect(cronOf(preset({ kind: 'custom', cron: '  ' }))).toBeNull()
  })

  test('a stored cron reads back as the preset that wrote it', () => {
    for (const p of [
      preset({ kind: 'hourly', minute: 45 }),
      preset({ kind: 'daily', time: '06:15' }),
      preset({ kind: 'weekdays', time: '09:00' }),
      preset({ kind: 'weekly', time: '17:30', weekday: 7 }),
      preset({ kind: 'weekly', time: '17:30', weekday: 3 }),
      preset({ kind: 'monthly', time: '12:00', monthDay: 15 }),
    ]) {
      const cron = cronOf(p)!
      expect(cronOf(presetOf(cron))).toBe(cron)
      expect(presetOf(cron).kind).toBe(p.kind)
    }
  })

  test('anything else stays raw cron in the expert field', () => {
    for (const cron of ['*/15 * * * *', '0 9 * * 1,3', '0 9 31 * *', '0 9 * 1 *', '0 9 * *']) {
      expect(presetOf(cron)).toMatchObject({ kind: 'custom', cron })
    }
  })
})
