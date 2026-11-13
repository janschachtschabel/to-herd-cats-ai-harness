import { describe, expect, test } from 'vitest'
import { extractHeadings, headingId, resolveWikiLinks, safeUrl } from './markdown'

describe('markdown helpers', () => {
  test('heading ids are readable and stable', () => {
    expect(headingId('Über uns & Kontakt')).toBe('ueber-uns-kontakt')
  })

  test('headings outside code fences, in order', () => {
    const md = '# Eins\n```\n# kein\n```\n## Zwei ##\ntext\n### Drei'
    expect(extractHeadings(md).map((h) => [h.level, h.text])).toEqual([
      [1, 'Eins'],
      [2, 'Zwei'],
      [3, 'Drei'],
    ])
  })

  test('wiki links resolve by title, unknown ones are marked missing', () => {
    const lookup = new Map([['handbuch', 'team/handbuch']])
    expect(resolveWikiLinks('Siehe [[Handbuch]] und [[Neu]].', lookup)).toBe(
      'Siehe [Handbuch](wiki:team%2Fhandbuch) und [Neu](wiki-missing:Neu).',
    )
    expect(resolveWikiLinks('```\n[[Handbuch]]\n```', lookup)).toBe('```\n[[Handbuch]]\n```')
  })

  test('only http, https, mailto and relative targets survive', () => {
    expect(safeUrl('https://example.com/a')).toBe('https://example.com/a')
    expect(safeUrl('mailto:a@b.de')).toBe('mailto:a@b.de')
    expect(safeUrl('/api/attachments/1')).toBe('/api/attachments/1')
    expect(safeUrl('#abschnitt')).toBe('#abschnitt')
    expect(safeUrl('javascript:alert(1)')).toBe('')
    expect(safeUrl(' JaVaScRiPt:alert(1)')).toBe('')
    expect(safeUrl('data:text/html,x')).toBe('')
    expect(safeUrl('vbscript:x')).toBe('')
  })
})
