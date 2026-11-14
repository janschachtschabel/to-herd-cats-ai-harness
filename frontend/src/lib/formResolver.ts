import type { FieldErrors, FieldValues, Resolver } from 'react-hook-form'
import type * as z from 'zod'

/**
 * A react-hook-form resolver for a form whose fields are not the request body itself
 * (a secret typed as "value" or "env", models one per line): the values are turned
 * into the body and checked against the body's schema (derived from openapi.json), and
 * each issue is reported at the field `fieldOf` names for its path.
 */
export function bodyResolver<V extends FieldValues>(
  schema: z.ZodType,
  toBody: (values: V) => unknown,
  fieldOf: (path: string) => string = (path) => path,
): Resolver<V> {
  return (values) => {
    const result = schema.safeParse(toBody(values))
    if (result.success) return { values, errors: {} }
    const errors: Record<string, { type: string; message: string }> = {}
    for (const issue of result.error.issues) {
      const field = fieldOf(issue.path.map(String).join('.'))
      errors[field] ??= { type: issue.code, message: issue.message }
    }
    return { values: {}, errors: errors as FieldErrors<V> }
  }
}
