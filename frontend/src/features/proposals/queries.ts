import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { wikiKeys } from '@/features/wiki/queries'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export type Proposal = Schemas['ProposalOut']
export type ProposalDetail = Schemas['ProposalDetailOut']
export type ProposalState = Schemas['ProposalState']

/** One list per space and state; `proposal.changed` refreshes a space's lists and the
 *  proposal (live events carry ids only). */
export const proposalKeys = {
  all: ['proposals'] as const,
  space: (spaceId: string) => ['proposals', 'list', spaceId] as const,
  list: (spaceId: string, state: ProposalState) => ['proposals', 'list', spaceId, state] as const,
  detail: (id: string) => ['proposals', 'detail', id] as const,
}

/** The open list asks for 100 at once: it also gives the tab's count and a page's hint. */
const PAGE = 100

export const proposalsQuery = (spaceId: string, state: ProposalState) =>
  pagedQuery(proposalKeys.list(spaceId, state), async (cursor) =>
    unwrap(
      await api.GET('/api/spaces/{space_id}/proposals', {
        params: { path: { space_id: spaceId }, query: { state, cursor, limit: PAGE } },
      }),
    ),
  )

/** A space's proposals the person sees (page editors; the list is empty for others,
 *  who therefore never ask). */
export function useProposals(spaceId: string, state: ProposalState, enabled = true) {
  return usePaged({ ...proposalsQuery(spaceId, state), enabled })
}

export const proposalQuery = (proposalId: string) =>
  queryOptions({
    queryKey: proposalKeys.detail(proposalId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/proposals/{proposal_id}', {
          params: { path: { proposal_id: proposalId } },
        }),
      ),
  })

export function useProposal(proposalId: string) {
  return useQuery(proposalQuery(proposalId))
}

/** After a decision (or a refused one): the proposal, the space's lists and, since an
 *  accepted change writes a page, everything of the wiki. */
function useRefresh(proposal: Proposal) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: proposalKeys.detail(proposal.id) })
    void queryClient.invalidateQueries({ queryKey: proposalKeys.space(proposal.space_id) })
    void queryClient.invalidateQueries({ queryKey: wikiKeys.all })
  }
}

export function useAcceptProposal(proposal: Proposal) {
  const refresh = useRefresh(proposal)
  return useMutation({
    mutationFn: async (body: Schemas['ProposalAcceptIn']) =>
      unwrap(
        await api.POST('/api/proposals/{proposal_id}/accept', {
          params: { path: { proposal_id: proposal.id } },
          body,
        }),
      ),
    onSettled: refresh,
  })
}

export function useRejectProposal(proposal: Proposal) {
  const refresh = useRefresh(proposal)
  return useMutation({
    mutationFn: async (body: Schemas['ProposalRejectIn']) =>
      unwrap(
        await api.POST('/api/proposals/{proposal_id}/reject', {
          params: { path: { proposal_id: proposal.id } },
          body,
        }),
      ),
    onSettled: refresh,
  })
}
