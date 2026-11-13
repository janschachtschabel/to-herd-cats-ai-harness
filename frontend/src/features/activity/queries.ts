import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { activityKeys } from '@/features/messaging/keys'
import { api, unwrap } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export const activityQuery = (includeDone: boolean) =>
  pagedQuery(activityKeys.list(includeDone), async (cursor) =>
    unwrap(
      await api.GET('/api/activity', {
        params: { query: { cursor, limit: 50, include_done: includeDone } },
      }),
    ),
  )

export const activityCountQuery = queryOptions({
  queryKey: activityKeys.count,
  queryFn: async () => unwrap(await api.GET('/api/activity/count')),
})

/** "For me": mentions and replies, newest first; done ones only with `includeDone`. */
export function useActivity(includeDone: boolean) {
  return usePaged(activityQuery(includeDone))
}

/** How many entries are not read yet (the badge and the window title). */
export function useActivityCount(): number {
  return useQuery(activityCountQuery).data?.unread ?? 0
}

function useActivityMutation(run: () => Promise<unknown>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: run,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: activityKeys.all }),
  })
}

export function useMarkActivityRead(notificationId: string) {
  return useActivityMutation(async () =>
    unwrap(
      await api.POST('/api/activity/{notification_id}/read', {
        params: { path: { notification_id: notificationId } },
      }),
    ),
  )
}

export function useMarkActivityDone(notificationId: string) {
  return useActivityMutation(async () =>
    unwrap(
      await api.POST('/api/activity/{notification_id}/done', {
        params: { path: { notification_id: notificationId } },
      }),
    ),
  )
}

export function useReadAllActivity() {
  return useActivityMutation(async () => unwrap(await api.POST('/api/activity/read-all')))
}
