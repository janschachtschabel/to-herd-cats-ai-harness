import { describe, expect, test } from 'vitest'
import { ApiError } from '@/lib/api'
import { makeSkillProposalDetail } from '@/test/skills'
import { movedFrom, movedOf } from './moved'

const now = { description: 'Jetzt.', content: 'jetzt' }
const proposed = { description: 'Neu.', content: 'neu' }

describe('a skill that moved on since the proposal', () => {
  test("is read from the 409's details, and from nothing else", () => {
    const error = new ApiError('skill_proposal.base_outdated', 409, 'x', null, {
      skill_version: 4,
      current: now,
      proposed,
    })
    expect(movedFrom(error)).toEqual({ skillVersion: 4, current: now, proposed })
    expect(movedFrom(new ApiError('skill_proposal.not_open', 409))).toBeNull()
    expect(movedFrom(new ApiError('skill_proposal.base_outdated', 409))).toBeNull()
    expect(movedFrom(new Error('x'))).toBeNull()
  })

  test('or from an open proposal that says so', () => {
    const outdated = makeSkillProposalDetail({
      outdated: true,
      current: { ...now, version: 7, number: 3 },
      proposed,
    })
    expect(movedOf(outdated)).toEqual({ skillVersion: 7, current: now, proposed })
    expect(movedOf({ ...outdated, outdated: false })).toBeNull()
    expect(movedOf({ ...outdated, state: 'accepted' })).toBeNull()
  })
})
