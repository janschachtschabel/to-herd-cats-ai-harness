import { describe, expect, test } from 'vitest'
import { keyNumber, ticketRefs } from './refs'

describe('ticket references', () => {
  test('keys and links, each once, in order, at most three', () => {
    expect(ticketRefs('Siehe HC-42 und hc-7, dann wieder HC-42.')).toEqual([42, 7])
    expect(ticketRefs('Link: https://herd.example/tickets/9 und /tickets/12')).toEqual([9, 12])
    expect(ticketRefs('HC-1 HC-2 HC-3 HC-4')).toEqual([1, 2, 3])
  })

  test('code, parts of words and other paths are not references', () => {
    expect(ticketRefs('`HC-42` und\n```\nHC-43\n```')).toEqual([])
    expect(ticketRefs('XHC-42 HC-42a HC-0 /api/tickets/5 abc/tickets/6')).toEqual([])
  })

  test('a key typed into the search', () => {
    expect(keyNumber(' HC-42 ')).toBe(42)
    expect(keyNumber('hc-7')).toBe(7)
    expect(keyNumber('42')).toBe(42)
    expect(keyNumber('HC 42')).toBeNull()
    expect(keyNumber('Urlaub 42')).toBeNull()
  })
})
