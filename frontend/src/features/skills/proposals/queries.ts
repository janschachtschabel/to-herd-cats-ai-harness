import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { skillKeys } from '@/features/skills/queries'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export type SkillProposal = Schemas['SkillProposalOut']
export type SkillProposalDetail = Schemas['SkillProposalDetailOut']
export type SkillProposalState = Schemas['SkillProposalState']

/** Which proposals a list shows: of one space, only organisation-wide, or all one
 *  sees; by state. */
export interface SkillProposalFilter {
  spaceId?: string
  orgWide?: boolean
  state: SkillProposalState
}

/** `skill_proposal.changed` (ids only) refreshes every list and the proposal. */
export const skillProposalKeys = {
  all: ['skill-proposals'] as const,
  list: (filter: SkillProposalFilter) => ['skill-proposals', 'list', filter] as const,
  detail: (id: string) => ['skill-proposals', 'detail', id] as const,
}

/** The open list asks for 100 at once: it also gives the tab's count. */
const PAGE = 100

export const skillProposalsQuery = (filter: SkillProposalFilter) =>
  pagedQuery(skillProposalKeys.list(filter), async (cursor) =>
    unwrap(
      await api.GET('/api/skill-proposals', {
        params: {
          query: {
            cursor,
            limit: PAGE,
            space_id: filter.spaceId,
            org_wide: filter.orgWide,
            state: filter.state,
          },
        },
      }),
    ),
  )

/** The proposals the person sees (whoever may decide them, and authors their own; the
 *  list is empty for anyone else, who therefore never asks). */
export function useSkillProposals(filter: SkillProposalFilter, enabled = true) {
  return usePaged({ ...skillProposalsQuery(filter), enabled })
}

export const skillProposalQuery = (proposalId: string) =>
  queryOptions({
    queryKey: skillProposalKeys.detail(proposalId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/skill-proposals/{proposal_id}', {
          params: { path: { proposal_id: proposalId } },
        }),
      ),
  })

export function useSkillProposal(proposalId: string) {
  return useQuery(skillProposalQuery(proposalId))
}

/** After a decision (or a refused one): the proposals and, since accepting writes a
 *  skill, the skills. */
function useRefresh() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: skillProposalKeys.all })
    void queryClient.invalidateQueries({ queryKey: skillKeys.all })
  }
}

export function useAcceptSkillProposal(proposalId: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: async (body: Schemas['SkillProposalAccept']) =>
      unwrap(
        await api.POST('/api/skill-proposals/{proposal_id}/accept', {
          params: { path: { proposal_id: proposalId } },
          body,
        }),
      ),
    onSettled: refresh,
  })
}

export function useRejectSkillProposal(proposalId: string) {
  const refresh = useRefresh()
  return useMutation({
    mutationFn: async (body: Schemas['SkillProposalReject']) =>
      unwrap(
        await api.POST('/api/skill-proposals/{proposal_id}/reject', {
          params: { path: { proposal_id: proposalId } },
          body,
        }),
      ),
    onSettled: refresh,
  })
}
