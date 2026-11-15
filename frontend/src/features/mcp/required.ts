import type { FieldErrors, FieldValues, Resolver } from 'react-hook-form'
import i18n from '@/lib/i18n'

/** A resolver that also reports the fields `missing` names as required (what the body's
 *  schema cannot say: a key for a new connector, a connector for a shared server). */
export function requiring<V extends FieldValues>(
  base: Resolver<V>,
  missing: (values: V) => string[],
): Resolver<V> {
  return async (values, context, options) => {
    const result = await base(values, context, options)
    const fields = missing(values)
    if (fields.length === 0) return result
    const errors: Record<string, { type: string; message: string }> = {}
    for (const field of fields) {
      errors[field] = { type: 'required', message: i18n.t('validation.required') }
    }
    return { values: {}, errors: { ...errors, ...result.errors } as FieldErrors<V> }
  }
}
