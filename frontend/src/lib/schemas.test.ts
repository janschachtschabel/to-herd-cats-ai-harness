import { describe, expect, test } from 'vitest'
import { components } from '../../openapi.json'
import i18n from './i18n'
import { bodySchema } from './schemas'

describe('form schemas from the OpenAPI document', () => {
  test('limits come from the backend schema', () => {
    const max = components.schemas.SpaceCreate.properties.name.maxLength
    const schema = bodySchema('SpaceCreate')
    expect(schema.safeParse({ kind: 'team', name: 'x'.repeat(max) }).success).toBe(true)
    expect(schema.safeParse({ kind: 'team', name: 'x'.repeat(max + 1) }).success).toBe(false)
    expect(schema.safeParse({ kind: 'secret', name: 'x' }).success).toBe(false)
  })

  test('messages are translated, with plural forms', async () => {
    const schema = bodySchema('UserCreate')
    const issues = (value: object) =>
      schema.safeParse(value).error?.issues.map((i) => [i.path.join('.'), i.message])
    expect(issues({ name: '', email: 'nope', password: 'short' })).toEqual([
      ['email', 'Bitte eine gültige E-Mail-Adresse eingeben.'],
      ['name', 'Bitte ausfüllen.'],
      ['password', 'Mindestens 10 Zeichen.'],
    ])
    await i18n.changeLanguage('en')
    expect(issues({ name: 'Jan', email: 'jan@example.com', password: 'short' })).toEqual([
      ['password', 'At least 10 characters.'],
    ])
  })

  test('unknown fields are refused where the backend refuses them', () => {
    expect(bodySchema('SpaceUpdateIn').safeParse({ version: 1, kind: 'open' }).success).toBe(false)
  })
})
