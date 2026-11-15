import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api'
import { invalidateTree } from '../queries'

/** Downloads are plain links (GET needs no CSRF header); the browser saves the file. */
export function spaceExportUrl(spaceId: string): string {
  return `/api/spaces/${encodeURIComponent(spaceId)}/export`
}

export function pageExportUrl(pageId: string): string {
  return `/api/pages/${encodeURIComponent(pageId)}/export`
}

/** A ZIP of Markdown files (and `_attachments/`) as the raw request body. */
export function useImportSpace(spaceId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) =>
      unwrap(
        await api.POST('/api/spaces/{space_id}/import', {
          params: { path: { space_id: spaceId } },
          body: file as unknown as string,
          bodySerializer: (body: unknown) => body as BodyInit,
          headers: { 'Content-Type': 'application/zip' },
        }),
      ),
    onSuccess: () => invalidateTree(queryClient, spaceId),
  })
}
