import { Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { ErrorState, LoadingState, PageHeader } from '@/features/shared/states'
import type { RemoteStatus } from '../display'
import { useServer } from '../serverQueries'
import { RemoteStatusText } from './RemoteResult'
import { ServerAccess } from './ServerAccess'
import { ServerActions } from './ServerActions'
import { ToolList } from './ToolList'

/** One external server (`ai.manage`): what it is, whose access it uses, what one can
 *  do with it, and its tools to approve one by one. `read`: the status of reading its
 *  tools right after it was added (a failure is named until the next refresh). */
export function ServerPage({ serverId, read }: { serverId: string; read?: RemoteStatus }) {
  const { t } = useTranslation()
  const server = useServer(serverId)
  const back = (
    <Link
      to="/admin/ai/mcp-servers"
      className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" aria-hidden />
      {t('mcp.servers.back')}
    </Link>
  )
  if (server.isPending) return <LoadingState />
  if (server.isError) {
    return (
      <div>
        {back}
        <ErrorState error={server.error} onRetry={() => void server.refetch()} />
      </div>
    )
  }
  const s = server.data
  return (
    <div className="flex flex-col gap-6">
      <div>
        {back}
        <PageHeader title={s.name} description={s.url}>
          <span className="mt-2 flex flex-wrap gap-1.5">
            <Badge variant="outline">
              {t('mcp.servers.dataLocationBadge', {
                location: t(`ai.locations.${s.data_location}`),
              })}
            </Badge>
            <Badge variant="outline">{t(`mcp.access.${s.connector_scope}`)}</Badge>
            {s.catalog_id && <Badge variant="outline">{t('mcp.servers.fromCatalog')}</Badge>}
            <Badge variant={s.enabled ? 'secondary' : 'destructive'}>
              {s.enabled ? t('mcp.servers.on') : t('mcp.servers.off')}
            </Badge>
          </span>
        </PageHeader>
        <ServerActions server={s} />
        {read && read !== 'ok' && <RemoteStatusText status={read} className="mt-2" />}
      </div>
      <ServerAccess server={s} />
      <section aria-labelledby="server-tools" className="flex flex-col gap-3">
        <div>
          <h2 id="server-tools" className="text-base font-semibold">
            {t('mcp.tools.title')}
          </h2>
          <p className="text-sm text-muted-foreground">{t('mcp.tools.hint')}</p>
        </div>
        <ToolList serverId={s.id} />
      </section>
    </div>
  )
}
