import * as z from 'zod'
import { components } from '../../openapi.json'
import type { Schemas } from './api'
import i18n from './i18n'

/**
 * Form validation derived from the backend's OpenAPI schemas (openapi.json, the same
 * file the TypeScript types are generated from), so limits such as `maxLength` are
 * never written twice. Messages come from i18n at validation time.
 */

type Json = { [key: string]: unknown }
const definitions = components.schemas as unknown as Record<string, Json>

/** The schema with every `$ref` replaced by its target (ours have no cycles). */
function inline(node: unknown): unknown {
  if (Array.isArray(node)) return node.map(inline)
  if (node === null || typeof node !== 'object') return node
  const { $ref, ...rest } = node as Json
  const own = Object.fromEntries(Object.entries(rest).map(([k, v]) => [k, inline(v)]))
  if (typeof $ref !== 'string') return own
  const target = definitions[$ref.split('/').at(-1) ?? '']
  if (!target) throw new Error(`unknown schema reference ${$ref}`)
  return { ...(inline(target) as Json), ...own }
}

/** The zod schema of a request body, e.g. `bodySchema('SpaceCreate')`. */
export function bodySchema<K extends keyof Schemas>(name: K): z.ZodType<Schemas[K], Schemas[K]> {
  const schema = definitions[name]
  if (!schema) throw new Error(`unknown schema ${String(name)}`)
  return z.fromJSONSchema(inline(schema) as z.core.JSONSchema.JSONSchema) as unknown as z.ZodType<
    Schemas[K],
    Schemas[K]
  >
}

/** For `register(field, { setValueAs: blankToNull })`: an empty optional field is null. */
export function blankToNull(value: unknown): unknown {
  return value === '' ? null : value
}

type Issue = z.core.$ZodRawIssue

function messageFor(issue: Issue): string {
  const t = i18n.t.bind(i18n)
  if (issue.input === '' && issue.code !== 'too_big') return t('validation.required')
  switch (issue.code) {
    case 'too_small':
      return Number(issue.minimum) <= 1
        ? t('validation.required')
        : t('validation.tooShort', { count: Number(issue.minimum) })
    case 'too_big':
      return t('validation.tooLong', { count: Number(issue.maximum) })
    case 'invalid_format':
      return issue.format === 'email' ? t('validation.email') : t('validation.invalid')
    case 'invalid_type':
      return issue.input === undefined || issue.input === null
        ? t('validation.required')
        : t('validation.invalid')
    case 'invalid_union': {
      // `string | null`: the string branch says what is wrong.
      const first = issue.errors[0]?.[0]
      return first ? messageFor(first as Issue) : t('validation.invalid')
    }
    default:
      return t('validation.invalid')
  }
}

z.config({ customError: (issue) => messageFor(issue) })
