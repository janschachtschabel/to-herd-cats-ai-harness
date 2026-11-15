import { Link, useNavigate } from '@tanstack/react-router'
import { BookOpen, ChevronRight, Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AiAdminTabs } from '@/features/ai/AiAdminTabs'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { cn } from '@/lib/utils'
import type { Server } from '../display'
import { useServers } from '../serverQueries'
import { ServerDialog } from './ServerDialog'

/** One server in the list: name, address, where data goes, whose access, on or off. */
function ServerItem({ server }: { server: Server }) {
  const { t } = useTranslation()
  return (
    <Link
      to="/admin/ai/mcp-servers/$serverId"
      params={{ serverId: server.id }}
      className={cn(
        'flex items-center gap-3 rounded-lg border p-4 hover:bg-accent/50 focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none',
        !server.enabled && 'bg-muted/40',
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="font-semibold break-words">{server.name}</p>
        <p className="text-xs break-all text-muted-foreground">{server.url}</p>
        <span className="mt-2 flex flex-wrap gap-1.5">
          <Badge variant="outline">{t(`ai.locations.${server.data_location}`)}</Badge>
          <Badge variant="outline">{t(`mcp.access.${server.connector_scope}`)}</Badge>
          {server.catalog_id && <Badge variant="outline">{t('mcp.servers.fromCatalog')}</Badge>}
          <Badge variant={server.enabled ? 'secondary' : 'destructive'}>
            {server.enabled ? t('mcp.servers.on') : t('mcp.servers.off')}
          </Badge>
        </span>
      </div>
      <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
    </Link>
  )
}

/** The external MCP servers (`ai.manage`): add one by its address or from the
 *  catalogue, then approve its tools one by one on its page. */
export function ServersPage() {
  const { t } = useTranslation()
  const servers = useServers()
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const add = (
    <Button onClick={() => setCreating(true)}>
      <Plus aria-hidden />
      {t('mcp.servers.create.open')}
    </Button>
  )
  return (
    <div>
      <PageHeader
        title={t('ai.title')}
        description={t('mcp.servers.description')}
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/admin/ai/catalog">
                <BookOpen aria-hidden />
                {t('mcp.servers.toCatalog')}
              </Link>
            </Button>
            {add}
          </>
        }
      />
      <AiAdminTabs />
      {servers.isPending ? (
        <LoadingState />
      ) : servers.isError ? (
        <ErrorState error={servers.error} onRetry={() => void servers.refetch()} />
      ) : servers.items.length === 0 ? (
        <EmptyState text={t('mcp.servers.empty')}>{add}</EmptyState>
      ) : (
        <ul className="flex flex-col gap-3" aria-label={t('mcp.servers.listLabel')}>
          {servers.items.map((server) => (
            <li key={server.id}>
              <ServerItem server={server} />
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={servers.hasMore} loading={servers.loadingMore} onLoad={servers.loadMore} />
      <ServerDialog
        open={creating}
        onOpenChange={setCreating}
        onCreated={(server) =>
          void navigate({
            to: '/admin/ai/mcp-servers/$serverId',
            params: { serverId: server.id },
            search: { read: server.refresh.status },
          })
        }
      />
    </div>
  )
}
