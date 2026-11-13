import { describe, expect, test } from 'vitest'
import { insertMention, mentionsIn, mentionToken, plainMentions, typedMention } from './mentions'

const LEA = { id: '0190a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b', name: 'Lea [Team] Löwe' }

describe('mentions', () => {
  test('a token carries the name without brackets and the id', () => {
    expect(mentionToken(LEA)).toBe(`@[Lea Team Löwe](user:${LEA.id})`)
  })

  test('the people of a text, each once, in order', () => {
    const text = `${mentionToken(LEA)} und @[Jan](user:${'1'.repeat(8)}-1111-7111-8111-${'1'.repeat(12)}) ${mentionToken(LEA)}`
    expect(mentionsIn(text).map((m) => m.name)).toEqual(['Lea Team Löwe', 'Jan'])
  })

  test('only an @ at a word start opens the picker, up to the caret', () => {
    expect(typedMention('Hallo @le', 9)).toEqual({ start: 6, query: 'le' })
    expect(typedMention('@', 1)).toEqual({ start: 0, query: '' })
    expect(typedMention('mail@example', 12)).toBeNull()
    expect(typedMention('Hallo @lea und', 14)).toBeNull()
  })

  test('a pick replaces the typed query and puts the caret behind the token', () => {
    const result = insertMention('Hi @le!', 3, 6, LEA)
    expect(result.text).toBe(`Hi ${mentionToken(LEA)} !`)
    expect(result.caret).toBe(3 + mentionToken(LEA).length + 1)
  })

  test('tokens read as @Name in short texts', () => {
    expect(plainMentions(`Frage an ${mentionToken(LEA)}`)).toBe('Frage an @Lea Team Löwe')
  })
})
