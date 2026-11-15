import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { aiKeys } from './keys'

/** How the organisation's usage is grouped: by day alone, or per day and key. */
export const USAGE_GROUPS = ['day', 'user', 'agent', 'space', 'connection'] as const
export type UsageGroup = (typeof USAGE_GROUPS)[number]

/** Usage sums per UTC day (`ai.manage`); `from`/`to` are days (YYYY-MM-DD). */
export function useUsage(by: UsageGroup, from: string, to: string) {
  return usePaged(
    pagedQuery(aiKeys.usage(by, from, to), async (cursor) =>
      unwrap(
        await api.GET('/api/ai/usage', {
          params: {
            query: { cursor, limit: 100, from, to, ...(by === 'day' ? {} : { by }) },
          },
        }),
      ),
    ),
  )
}

/** My own usage of the last 30 days (`ai.use`; asked only while `enabled`). */
export function useMyUsage(enabled: boolean) {
  return useQuery({
    queryKey: aiKeys.myUsage,
    queryFn: async () => unwrap(await api.GET('/api/ai/usage/me')),
    enabled,
  })
}
