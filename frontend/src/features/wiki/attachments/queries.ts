import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export const attachmentsQuery = (pageId: string) =>
  pagedQuery(['wiki', 'attachments', pageId], async (cursor) =>
    unwrap(
      await api.GET('/api/pages/{page_id}/attachments', {
        params: { path: { page_id: pageId }, query: { cursor } },
      }),
    ),
  )

export function useAttachments(pageId: string) {
  return usePaged(attachmentsQuery(pageId))
}

/** The file is the raw request body; its name travels in `?filename=`. */
export function useUploadAttachment(pageId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) =>
      unwrap(
        await api.POST('/api/pages/{page_id}/attachments', {
          params: { path: { page_id: pageId }, query: { filename: file.name } },
          body: file as unknown as string,
          bodySerializer: (body: unknown) => body as BodyInit,
          headers: { 'Content-Type': 'application/octet-stream' },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: attachmentsQuery(pageId).queryKey }),
  })
}

export function useDeleteAttachment(pageId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (attachmentId: string) =>
      unwrap(
        await api.DELETE('/api/attachments/{attachment_id}', {
          params: { path: { attachment_id: attachmentId } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: attachmentsQuery(pageId).queryKey }),
  })
}
