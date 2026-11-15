import { describe, expect, test } from 'vitest'
import { summarizeDetails } from './describe'

describe('audit details', () => {
  test('changes read as from → to; member ids are left out', () => {
    expect(
      summarizeDetails({
        changes: { name: { from: 'A', to: 'B' }, icon: { from: null, to: '📁' } },
      }),
    ).toBe('name: A → B, icon: – → 📁')
    expect(summarizeDetails({ member_type: 'group', member_id: 'x', role: 'editor' })).toBe(
      'member_type: group, role: editor',
    )
    expect(summarizeDetails(null)).toBe('')
  })
})
