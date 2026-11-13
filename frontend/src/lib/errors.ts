import type { TFunction } from 'i18next'
import { ApiError } from './api'

/** A translated sentence for an error: the backend code's own text if there is one. */
export function errorMessage(t: TFunction, error: unknown): string {
  if (error instanceof ApiError) {
    const own = t(`errors.${error.code}`, { defaultValue: '' })
    if (own) return own
    if (error.status === 403) return t('errors.forbidden')
    if (error.status === 404) return t('errors.notFound')
    if (error.status === 413) return t('errors.tooLarge')
    if (error.status === 415) return t('errors.unsupportedType')
    return t('errors.generic')
  }
  return t('errors.network')
}

/** What the backend said, for the small print: its message and the trace id. */
export function errorDetails(error: unknown): { message: string; traceId: string | null } | null {
  if (!(error instanceof ApiError)) return null
  return { message: error.message, traceId: error.traceId }
}
