import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { agentsQuery } from '@/features/agents/queries'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import type { BudgetTarget } from './budgets/budget'
import { aiKeys } from './keys'

/** The daily budgets with today's use (`ai.manage`). */
export const budgetsQuery = pagedQuery(aiKeys.budgets, async (cursor) =>
  unwrap(await api.GET('/api/ai/budgets', { params: { query: { cursor, limit: 100 } } })),
)

export function useBudgets() {
  return usePaged(budgetsQuery)
}

/** A budget as the server has it now (after a conflict); undefined once it is gone. */
export function useFreshBudget() {
  const queryClient = useQueryClient()
  return async (id: string) => {
    const data = await queryClient.fetchInfiniteQuery({ ...budgetsQuery, staleTime: 0 })
    return data.pages.flatMap((p) => p.items).find((budget) => budget.id === id)
  }
}

/** The agents a budget may name (`agent.manage`; asked only while `enabled`). */
export function useBudgetAgents(enabled: boolean) {
  const query = useInfiniteQuery({ ...agentsQuery, enabled })
  return {
    items: query.data?.pages.flatMap((p) => p.items) ?? [],
    isPending: query.isPending && enabled,
    error: query.error,
    hasMore: query.hasNextPage,
    loadingMore: query.isFetchingNextPage,
    loadMore: () => void query.fetchNextPage(),
  }
}

function putBudget(target: BudgetTarget, body: Schemas['BudgetIn']) {
  if (target.scope === 'organisation') return api.PUT('/api/ai/budgets/organisation', { body })
  if (target.scope === 'user') {
    return api.PUT('/api/ai/budgets/users/{user_id}', {
      params: { path: { user_id: target.id } },
      body,
    })
  }
  return api.PUT('/api/ai/budgets/agents/{agent_id}', {
    params: { path: { agent_id: target.id } },
    body,
  })
}

/** Sets a budget: `version` null creates, else the version read (409 when stale). */
export function useSetBudget() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ target, body }: { target: BudgetTarget; body: Schemas['BudgetIn'] }) =>
      unwrap(await putBudget(target, body)),
    onSettled: () => queryClient.invalidateQueries({ queryKey: aiKeys.budgets }),
  })
}

export function useRemoveBudget() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, version }: { id: string; version: number }) =>
      unwrap(
        await api.DELETE('/api/ai/budgets/{budget_id}', {
          params: { path: { budget_id: id }, query: { version } },
        }),
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: aiKeys.budgets }),
  })
}
