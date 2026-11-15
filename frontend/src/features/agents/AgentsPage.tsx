import { Globe, Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { useConnections } from '@/features/ai/queries'
import { hasPermission, useMe } from '@/features/auth/queries'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { AgentCard } from './AgentCard'
import { AgentDialog } from './AgentDialog'
import { ExternalAgentDialog } from './external/ExternalAgentDialog'
import { useAgents, type Agent } from './queries'

/** The agents (`agent.manage`): create, change, pause. A connection to answer with
 *  comes from the AI administration (`ai.manage`). */
export function AgentsPage() {
  const { t } = useTranslation()
  const me = useMe()
  const agents = useAgents()
  const connections = useConnections(hasPermission(me, 'ai.manage'))
  const [creating, setCreating] = useState(false)
  const [creatingExternal, setCreatingExternal] = useState(false)
  const [editing, setEditing] = useState<Agent | null>(null)
  const external = editing?.kind === 'external'
  const noConnection = !connections.isPending && connections.items.length === 0
  const names = new Map(connections.items.map((c) => [c.id, c.name]))

  return (
    <div>
      <PageHeader
        title={t('agents.title')}
        description={t('agents.description')}
        actions={
          <>
            <Button variant="outline" onClick={() => setCreatingExternal(true)}>
              <Globe aria-hidden />
              {t('agents.external.create')}
            </Button>
            <Button onClick={() => setCreating(true)} disabled={noConnection}>
              <Plus aria-hidden />
              {t('agents.create.open')}
            </Button>
          </>
        }
      />
      {noConnection && (
        <p className="mb-4 rounded-md border border-dashed p-3 text-sm text-muted-foreground">
          {t('agents.noConnection')}
        </p>
      )}
      {agents.isPending ? (
        <LoadingState />
      ) : agents.isError ? (
        <ErrorState error={agents.error} onRetry={() => void agents.refetch()} />
      ) : agents.items.length === 0 ? (
        <EmptyState text={t('agents.empty')} />
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2" aria-label={t('agents.listLabel')}>
          {agents.items.map((agent) => (
            <li key={agent.id}>
              <AgentCard
                agent={agent}
                connectionName={
                  agent.connection_id ? (names.get(agent.connection_id) ?? null) : null
                }
                onEdit={() => setEditing(agent)}
              />
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={agents.hasMore} loading={agents.loadingMore} onLoad={agents.loadMore} />
      <AgentDialog open={creating} connections={connections.items} onOpenChange={setCreating} />
      <ExternalAgentDialog open={creatingExternal} onOpenChange={setCreatingExternal} />
      <ExternalAgentDialog
        key={`external-${editing?.id ?? 'none'}`}
        open={editing !== null && external}
        agent={external ? editing : undefined}
        onOpenChange={(open) => !open && setEditing(null)}
      />
      <AgentDialog
        key={editing?.id ?? 'none'}
        open={editing !== null && !external}
        agent={editing && !external ? editing : undefined}
        connections={connections.items}
        onOpenChange={(open) => !open && setEditing(null)}
      />
    </div>
  )
}
