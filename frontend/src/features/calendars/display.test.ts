import { describe, expect, test } from 'vitest'
import i18n from '@/lib/i18n'
import { makeOccurrence } from '@/test/calendars'
import { calendarLabel, chipTime, whenText } from './display'

const t = i18n.t.bind(i18n)

describe('what an occurrence shows', () => {
  const night = makeOccurrence({ start: '2026-11-19T22:00:00Z', end: '2026-11-21T02:00:00Z' })

  test('a chip shows the start only on the day it starts, then how it goes on', () => {
    expect(chipTime(t, night, '2026-11-19', 'UTC', 'de')).toBe('22:00')
    expect(chipTime(t, night, '2026-11-20', 'UTC', 'de')).toBe('Fortsetzung')
    expect(chipTime(t, night, '2026-11-21', 'UTC', 'de')).toBe('bis 02:00')
    expect(chipTime(t, night, undefined, 'UTC', 'de')).toBe('22:00')
    expect(chipTime(t, makeOccurrence({ all_day: true }), '2026-11-19', 'UTC', 'de')).toBeNull()
  })

  test('the look names the whole span of an all-day event of several days', () => {
    const fair = makeOccurrence({
      all_day: true,
      start: '2026-11-19T00:00:00Z',
      end: '2026-11-22T00:00:00Z',
    })
    // Intl puts thin spaces around the dash.
    expect(whenText(t, fair, 'America/Los_Angeles', 'de')).toMatch(
      /^Donnerstag, 19\.\s–\sSamstag, 21\. November 2026, ganztägig$/,
    )
    const one = makeOccurrence({
      all_day: true,
      start: '2026-11-19T00:00:00Z',
      end: '2026-11-20T00:00:00Z',
    })
    expect(whenText(t, one, 'UTC', 'de')).toBe('Donnerstag, 19. November 2026, ganztägig')
    expect(whenText(t, makeOccurrence(), 'UTC', 'de')).toBe(
      'Donnerstag, 19. November 2026, 09:00–10:00 Uhr',
    )
  })

  test('a calendar the list does not hold is named neutrally', async () => {
    expect(calendarLabel(t, undefined)).toBe('Kalender')
    await i18n.changeLanguage('en')
    expect(calendarLabel(t, undefined)).toBe('Calendar')
    await i18n.changeLanguage('de')
  })
})
