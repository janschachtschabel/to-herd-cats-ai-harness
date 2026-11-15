import { describe, expect, test } from 'vitest'
import { lineDiff } from './diff'

describe('a line diff of two skill texts', () => {
  test('keeps equal lines and marks what was deleted and inserted', () => {
    expect(lineDiff('a\nb\nc', 'a\nB\nc\nd')).toEqual([
      { kind: 'equal', lines: ['a'] },
      { kind: 'delete', lines: ['b'] },
      { kind: 'insert', lines: ['B'] },
      { kind: 'equal', lines: ['c'] },
      { kind: 'insert', lines: ['d'] },
    ])
  })

  test('the same text is one equal run; an empty side is all inserted or deleted', () => {
    expect(lineDiff('x\ny', 'x\ny')).toEqual([{ kind: 'equal', lines: ['x', 'y'] }])
    expect(lineDiff('', 'neu')).toEqual([{ kind: 'insert', lines: ['neu'] }])
    expect(lineDiff('alt', '')).toEqual([{ kind: 'delete', lines: ['alt'] }])
  })

  test('texts too long to compare line by line are shown as replaced', () => {
    const many = (prefix: string) =>
      Array.from({ length: 3000 }, (_, i) => `${prefix}${i}`).join('\n')
    const hunks = lineDiff(many('a'), many('b'))
    expect(hunks.map((h) => h.kind)).toEqual(['delete', 'insert'])
  })
})
