import { useMutation } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

const keys = {
  dms: (userId: string) => ['admin', 'dm-inspect', 'dms', userId] as const,
  messages: (inspectionId: string) => ['admin', 'dm-inspect', 'messages', inspectionId] as const,
}

/** A person's direct messages (who with, when last written), never their content.
 *  The first page is audited (`dm.admin_lookup`). */
export function useInspectableDms(userId: string) {
  return usePaged(
    pagedQuery(keys.dms(userId), async (cursor) =>
      unwrap(
        await api.GET('/api/admin/dm-inspect', {
          params: { query: { user_id: userId, cursor, limit: 50 } },
        }),
      ),
    ),
  )
}

/** Asks to read one direct message, with a reason (audited; the participants see it). */
export function useGrantInspection() {
  return useMutation({
    mutationFn: async (body: { conversation_id: string; reason: string }) =>
      unwrap(await api.POST('/api/admin/dm-inspect', { body })),
  })
}

/** The messages an inspection lets one read (replies too), newest first, until it
 *  expires (then 404 `dm_inspection.not_found`). */
export function useInspectedMessages(inspectionId: string) {
  return usePaged(
    pagedQuery(keys.messages(inspectionId), async (cursor) =>
      unwrap(
        await api.GET('/api/admin/dm-inspect/{inspection_id}/messages', {
          params: { path: { inspection_id: inspectionId }, query: { cursor, limit: 50 } },
        }),
      ),
    ),
  )
}
