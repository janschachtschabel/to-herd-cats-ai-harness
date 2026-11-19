import { afterEach, describe, expect, test } from 'vitest'
import { calendarName } from '@/features/calendars/name'
import i18n from '@/lib/i18n'

const t = i18n.t.bind(i18n)

describe('calendar names', () => {
  afterEach(async () => {
    await i18n.changeLanguage('de')
  })

  test('a default calendar nobody renamed is named in the reader’s language', async () => {
    const unnamed = { name: null, is_default: true }
    expect(calendarName(t, unnamed, 'personal')).toBe('Mein Kalender')
    expect(calendarName(t, unnamed, 'open')).toBe('Allgemein')
    await i18n.changeLanguage('en')
    expect(calendarName(t, unnamed, 'personal')).toBe('My calendar')
    expect(calendarName(t, unnamed, 'open')).toBe('General')
  })

  test('while its space is unknown a default calendar is not named from a guess', async () => {
    const unnamed = { name: null, is_default: true }
    expect(calendarName(t, unnamed, undefined)).toBe('Standardkalender')
    await i18n.changeLanguage('en')
    expect(calendarName(t, unnamed, undefined)).toBe('Default calendar')
  })

  test('a name someone gave is shown as given', () => {
    expect(calendarName(t, { name: 'Urlaub', is_default: false }, 'team')).toBe('Urlaub')
    expect(calendarName(t, { name: 'Privat', is_default: true }, 'personal')).toBe('Privat')
  })
})
