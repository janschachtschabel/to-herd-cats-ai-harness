import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/queries'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { AgentCard } from '../AgentCard'
import type { Agent } from '../queries'
import { PersonalAgentDialog } from './PersonalAgentDialog'
import { createsPersonal, useMyAgents } from './queries'

/** "Meine Agenten": one's personal agents (they work only in one's personal space, at
 *  most level 2, and count on one's own account): make, change, pause, delete, talk.
 *  Switched off by the organisation, the page says so and offers nothing new. */
export function MyAgentsPage() {
  const { t } = useTranslation()
  const me = useMe()
  const agents = useMyAgents(me?.user.id)
  const allowed = createsPersonal(me)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Agent | null>(null)
  return (
    <div>
      <PageHeader
        title={t('agents.personal.title')}
        description={t('agents.personal.description')}
        actions={
          allowed && (
            <Button onClick={() => setCreating(true)}>
              <Plus aria-hidden />
              {t('agents.personal.create')}
            </Button>
          )
        }
      />
      {!allowed && (
        <p
          role="status"
          className="mb-4 rounded-md border border-dashed p-3 text-sm text-muted-foreground"
        >
          {t('agents.personal.disabled')}
        </p>
      )}
      {agents.isPending ? (
        <LoadingState />
      ) : agents.isError ? (
        <ErrorState error={agents.error} onRetry={() => void agents.refetch()} />
      ) : agents.items.length === 0 && !agents.hasMore ? (
        <EmptyState text={t('agents.personal.empty')} />
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2" aria-label={t('agents.personal.listLabel')}>
          {agents.items.map((agent) => (
            <li key={agent.id}>
              <AgentCard
                agent={agent}
                connectionName={null}
                onEdit={() => setEditing(agent)}
                mine
              />
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={agents.hasMore} loading={agents.loadingMore} onLoad={agents.loadMore} />
      <PersonalAgentDialog open={creating} onOpenChange={setCreating} />
      <PersonalAgentDialog
        key={editing?.id ?? 'none'}
        open={editing !== null}
        agent={editing ?? undefined}
        onOpenChange={(open) => !open && setEditing(null)}
      />
    </div>
  )
}
