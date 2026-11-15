import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { agentKeys } from '@/features/agents/keys'
import { activityKeys } from '@/features/messaging/keys'
import { api, ApiError, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export type Approval = Schemas['ApprovalOut']
export type Question = Schemas['QuestionOut']

/** The keys of a run's cards. A decided card refreshes all of them (`card.changed`). */
export const approvalKeys = {
  all: ['approvals'] as const,
  detail: (id: string) => ['approvals', 'detail', id] as const,
  diff: (id: string) => ['approvals', 'diff', id] as const,
  /** Mine to decide (the list "Freigaben" and its count). */
  mine: ['approvals', 'mine'] as const,
  question: (id: string) => ['approvals', 'question', id] as const,
}

/** A card one may not see answers 404: asked once, never again (it shows without
 *  actions); anything else is tried once more. */
function retryUnlessHidden(count: number, error: unknown): boolean {
  return !(error instanceof ApiError && error.status === 404) && count < 1
}

export function useApproval(approvalId: string) {
  return useQuery({
    queryKey: approvalKeys.detail(approvalId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/approvals/{approval_id}', {
          params: { path: { approval_id: approvalId } },
        }),
      ),
    retry: retryUnlessHidden,
  })
}

/** A page's diff (the page now against the call's content), for the person asked;
 *  null when the texts are too large to compare. Asked only while shown. */
export function useApprovalDiff(approvalId: string, enabled: boolean) {
  return useQuery({
    queryKey: approvalKeys.diff(approvalId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/approvals/{approval_id}/diff', {
          params: { path: { approval_id: approvalId } },
        }),
      ),
    enabled,
  })
}

function useCardDone() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: approvalKeys.mine })
    void queryClient.invalidateQueries({ queryKey: activityKeys.all })
    void queryClient.invalidateQueries({ queryKey: agentKeys.runs })
  }
}

/** Approve or reject (with an optional reason) at the version the card shows; any 409
 *  reloads the card, so it shows what happened instead. */
export function useDecideApproval(approvalId: string) {
  const queryClient = useQueryClient()
  const done = useCardDone()
  return useMutation({
    mutationFn: async (body: Schemas['ApprovalDecide']) =>
      unwrap(
        await api.POST('/api/approvals/{approval_id}/decide', {
          params: { path: { approval_id: approvalId } },
          body,
        }),
      ),
    onSuccess: (approval) => {
      queryClient.setQueryData(approvalKeys.detail(approvalId), approval)
      done()
    },
    onError: () => {
      void queryClient.invalidateQueries({ queryKey: approvalKeys.detail(approvalId) })
      done()
    },
  })
}

export function useQuestion(questionId: string) {
  return useQuery({
    queryKey: approvalKeys.question(questionId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/questions/{question_id}', {
          params: { path: { question_id: questionId } },
        }),
      ),
    retry: retryUnlessHidden,
  })
}

export function useAnswerQuestion(questionId: string) {
  const queryClient = useQueryClient()
  const done = useCardDone()
  return useMutation({
    mutationFn: async (body: Schemas['QuestionAnswer']) =>
      unwrap(
        await api.POST('/api/questions/{question_id}/answer', {
          params: { path: { question_id: questionId } },
          body,
        }),
      ),
    onSuccess: (question) => {
      queryClient.setQueryData(approvalKeys.question(questionId), question)
      done()
    },
    onError: () => {
      void queryClient.invalidateQueries({ queryKey: approvalKeys.question(questionId) })
      done()
    },
  })
}

/** The releases waiting for me, newest first. */
export const myApprovalsQuery = (state: Schemas['ApprovalState'] | undefined) =>
  pagedQuery([...approvalKeys.mine, state ?? 'all'], async (cursor) =>
    unwrap(await api.GET('/api/approvals', { params: { query: { cursor, limit: 50, state } } })),
  )

export function useMyApprovals(state: Schemas['ApprovalState'] | undefined) {
  return usePaged(myApprovalsQuery(state))
}

/** How many releases wait for me (the first page counts; more shows as "50+"). */
export function usePendingApprovalCount(enabled: boolean): { count: number; more: boolean } {
  const query = useQuery({
    queryKey: [...approvalKeys.mine, 'pending', 'count'],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/approvals', { params: { query: { state: 'pending', limit: 50 } } }),
      ),
    enabled,
  })
  return { count: query.data?.items.length ?? 0, more: Boolean(query.data?.next_cursor) }
}
