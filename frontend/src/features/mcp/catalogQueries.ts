import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, unwrap, type Schemas } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'
import { mcpKeys } from './keys'

/** The catalogue of server templates (`ai.manage`). */
export function useCatalog() {
  return usePaged(
    pagedQuery(mcpKeys.catalog, async (cursor) =>
      unwrap(await api.GET('/api/ai/mcp-catalog', { params: { query: { cursor, limit: 100 } } })),
    ),
  )
}

/** Operator files that could not be read (file and place of the error, no content). */
export function useCatalogProblems() {
  return usePaged(
    pagedQuery(mcpKeys.catalogProblems, async (cursor) =>
      unwrap(
        await api.GET('/api/ai/mcp-catalog/problems', {
          params: { query: { cursor, limit: 100 } },
        }),
      ),
    ),
  )
}

/** A server (and its connector or OAuth app) from a template, in one step; every tool
 *  still comes in pending. The variables may carry a key: forgotten at once. */
export function useInstallEntry(entryId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    gcTime: 0,
    mutationFn: async (body: Schemas['InstallIn']) =>
      unwrap(
        await api.POST('/api/ai/mcp-catalog/{entry_id}/install', {
          params: { path: { entry_id: entryId } },
          body,
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: mcpKeys.servers })
      void queryClient.invalidateQueries({ queryKey: mcpKeys.connectors })
      void queryClient.invalidateQueries({ queryKey: mcpKeys.clients })
      void queryClient.invalidateQueries({ queryKey: mcpKeys.myServers })
    },
  })
}
