import { ApiError, type Schemas } from '@/lib/api'
import type { Proposal, ProposalDetail } from './queries'

export type Segment = Schemas['ProposalSegmentOut']

/** How one conflict region is resolved: keep the page as it is now, take the proposal,
 *  or both (the page's lines, then the proposal's). */
export type Choice = 'current' | 'proposed' | 'both'

/** What accepting a proposal needs once its page moved on: the page's `version` to
 *  name, the clean merge (null with conflicts) and the merge as segments; `tooLarge`
 *  when the texts are beyond the server's limit (no merge offered). */
export interface Outdated {
  pageVersion: number
  mergedContent: string | null
  segments: Segment[]
  tooLarge: boolean
}

function isSegment(value: unknown): value is Segment {
  if (typeof value !== 'object' || value === null) return false
  const s = value as Record<string, unknown>
  return (s.kind === 'clean' || s.kind === 'conflict') && Array.isArray(s.lines ?? [])
}

function lines(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((l): l is string => typeof l === 'string') : []
}

/** The merge in a 409 `proposal.base_outdated`, or null for any other error. */
export function outdatedFrom(error: unknown): Outdated | null {
  if (!(error instanceof ApiError) || error.code !== 'proposal.base_outdated') return null
  const d = error.details ?? {}
  if (typeof d.current_version !== 'number') return null
  const segments = Array.isArray(d.segments) ? d.segments.filter(isSegment) : []
  return {
    pageVersion: d.current_version,
    mergedContent: typeof d.merged_content === 'string' ? d.merged_content : null,
    segments: segments.map((s) => ({
      kind: s.kind,
      lines: lines(s.lines),
      base: lines(s.base),
      proposed: lines(s.proposed),
      current: lines(s.current),
    })),
    tooLarge: d.too_large === true,
  }
}

/** The same from a proposal's detail: null while its page still holds the base. */
export function outdatedOf(detail: ProposalDetail): Outdated | null {
  if (detail.state !== 'open' || detail.current_content_md === null) return null
  if (detail.page_version === null) return null
  return {
    pageVersion: detail.page_version,
    mergedContent: detail.merge?.merged_content ?? null,
    segments: detail.merge?.segments ?? [],
    tooLarge: detail.merge === null,
  }
}

/** The conflict regions in order; a choice is kept per region by this index. */
export function conflictsOf(segments: readonly Segment[]): Segment[] {
  return segments.filter((s) => s.kind === 'conflict')
}

export function conflictCount(segments: readonly Segment[]): number {
  return conflictsOf(segments).length
}

/** The text the segments make with a choice per conflict region (by its index among
 *  the conflicts; unchosen ones keep the page as it is now). Lines are joined as the
 *  server joins a clean merge. */
export function mergedText(segments: readonly Segment[], choices: readonly Choice[]): string {
  let conflict = 0
  const out: string[] = []
  for (const segment of segments) {
    if (segment.kind === 'clean') {
      out.push(...segment.lines)
      continue
    }
    const choice = choices[conflict] ?? 'current'
    conflict += 1
    if (choice !== 'proposed') out.push(...segment.current)
    if (choice !== 'current') out.push(...segment.proposed)
  }
  return out.join('\n')
}

/** The text to start the moderator's edit from: the clean merge, else the choices. */
export function startText(outdated: Outdated, choices: readonly Choice[]): string {
  return outdated.mergedContent ?? mergedText(outdated.segments, choices)
}

/** Whether accept and reject are offered: open proposals, to moderators. */
export function decidable(proposal: Proposal, moderate: boolean): boolean {
  return moderate && proposal.state === 'open'
}
