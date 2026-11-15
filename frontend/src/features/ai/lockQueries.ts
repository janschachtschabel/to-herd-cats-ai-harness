import { useMutation, useQueryClient } from '@tanstack/react-query'
import { attachmentsQuery } from '@/features/wiki/attachments/queries'
import { refetchOnConflict, storePage } from '@/features/wiki/queries'
import { api, unwrap, type Attachment, type WikiPage } from '@/lib/api'

/** Locks a page for AI or lifts the lock (`page.moderate`); 409 on a stale version. */
export function useSetPageAiLock(page: WikiPage) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (noAi: boolean) =>
      unwrap(
        await api.PUT('/api/pages/{page_id}/ai-lock', {
          params: { path: { page_id: page.id } },
          body: { no_ai: noAi, version: page.version },
        }),
      ),
    onSuccess: (fresh) => storePage(queryClient, fresh),
    onError: (error) => refetchOnConflict(queryClient, page, error),
  })
}

/** The same for one file of a page. */
export function useSetAttachmentAiLock(pageId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (attachment: Attachment) =>
      unwrap(
        await api.PUT('/api/attachments/{attachment_id}/ai-lock', {
          params: { path: { attachment_id: attachment.id } },
          body: { no_ai: !attachment.no_ai, version: attachment.version },
        }),
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: attachmentsQuery(pageId).queryKey }),
  })
}
