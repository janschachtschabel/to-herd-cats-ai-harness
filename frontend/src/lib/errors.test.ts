import { afterEach, describe, expect, test } from 'vitest'
import i18n, { setLocale } from '@/lib/i18n'
import { ApiError } from './api'
import { errorMessage } from './errors'

describe('errorMessage', () => {
  afterEach(() => setLocale('de'))

  // A store that does not answer (S3, plan M9 Task 14) and an installation in
  // maintenance (Task 12) are temporary: say so, in both languages.
  test.each([
    ['storage.unavailable', 503],
    ['maintenance.active', 503],
    ['rate.limited', 429],
    ['attachment.rejected_by_scan', 422],
    ['attachment.scan_unavailable', 503],
  ])('%s has its own text', (code, status) => {
    const t = i18n.t.bind(i18n)
    for (const locale of ['de', 'en'] as const) {
      setLocale(locale)
      const text = errorMessage(t, new ApiError(code, status))
      expect(text).not.toBe(t('errors.generic'))
      expect(text).toBe(t(`errors.${code}`))
    }
  })
})
