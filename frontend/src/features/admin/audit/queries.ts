import { api, unwrap } from '@/lib/api'
import { pagedQuery, usePaged } from '@/lib/paging'

export interface AuditFilter {
  actorId?: string
  action?: string
}

export const auditQuery = (filter: AuditFilter) =>
  pagedQuery(['admin', 'audit', filter], async (cursor) =>
    unwrap(
      await api.GET('/api/admin/audit', {
        params: { query: { cursor, actor_id: filter.actorId, action: filter.action } },
      }),
    ),
  )

export function useAudit(filter: AuditFilter) {
  return usePaged(auditQuery(filter))
}
