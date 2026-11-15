import { describe, expect, test } from 'vitest'
import { ApiError } from '@/lib/api'
import { conflictCount, mergedText, outdatedFrom, type Segment } from './merge'

const segments: Segment[] = [
  { kind: 'clean', lines: ['# Urlaub', ''], base: [], proposed: [], current: [] },
  {
    kind: 'conflict',
    lines: [],
    base: ['30 Tage.'],
    proposed: ['32 Tage.'],
    current: ['31 Tage.'],
  },
  { kind: 'clean', lines: ['', 'Antrag im Portal.'], base: [], proposed: [], current: [] },
]

describe('the merge of a proposal whose page moved on', () => {
  test('a conflict keeps the page unless chosen otherwise', () => {
    expect(mergedText(segments, [])).toBe('# Urlaub\n\n31 Tage.\n\nAntrag im Portal.')
    expect(mergedText(segments, ['proposed'])).toBe('# Urlaub\n\n32 Tage.\n\nAntrag im Portal.')
    expect(mergedText(segments, ['both'])).toBe(
      '# Urlaub\n\n31 Tage.\n32 Tage.\n\nAntrag im Portal.',
    )
    expect(conflictCount(segments)).toBe(1)
  })

  test('the 409 details are read defensively', () => {
    const error = new ApiError('proposal.base_outdated', 409, 'outdated', null, {
      current_version: 7,
      too_large: false,
      merged_content: null,
      segments: [...segments, { kind: 'nonsense' }],
    })
    expect(outdatedFrom(error)).toEqual({
      pageVersion: 7,
      mergedContent: null,
      segments,
      tooLarge: false,
    })
    expect(outdatedFrom(new ApiError('proposal.not_open', 409))).toBeNull()
    expect(outdatedFrom(new ApiError('proposal.base_outdated', 409))).toBeNull()
  })
})
