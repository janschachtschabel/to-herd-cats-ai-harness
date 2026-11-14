import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import type { Connection } from '../display'
import { useConnections } from '../queries'
import { AiAdminTabs } from '../AiAdminTabs'
import { ConnectionCard } from './ConnectionCard'
import { ConnectionDialog } from './ConnectionDialog'

/** The AI connections (`ai.manage`): set up, test, switch on and off. */
export function ConnectionsPage() {
  const { t } = useTranslation()
  const connections = useConnections()
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Connection | null>(null)

  return (
    <div>
      <PageHeader
        title={t('ai.title')}
        description={t('ai.connections.description')}
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden />
            {t('ai.connections.create.open')}
          </Button>
        }
      />
      <AiAdminTabs />
      {connections.isPending ? (
        <LoadingState />
      ) : connections.isError ? (
        <ErrorState error={connections.error} onRetry={() => void connections.refetch()} />
      ) : connections.items.length === 0 ? (
        <EmptyState text={t('ai.connections.empty')}>
          <Button variant="outline" onClick={() => setCreating(true)}>
            {t('ai.connections.create.open')}
          </Button>
        </EmptyState>
      ) : (
        <ul className="flex flex-col gap-3" aria-label={t('ai.connections.listLabel')}>
          {connections.items.map((connection) => (
            <li key={connection.id}>
              <ConnectionCard connection={connection} onEdit={() => setEditing(connection)} />
            </li>
          ))}
        </ul>
      )}
      <LoadMore
        hasMore={connections.hasMore}
        loading={connections.loadingMore}
        onLoad={connections.loadMore}
      />
      <ConnectionDialog open={creating} onOpenChange={setCreating} />
      <ConnectionDialog
        key={editing?.id ?? 'none'}
        open={editing !== null}
        connection={editing ?? undefined}
        onOpenChange={(open) => !open && setEditing(null)}
      />
    </div>
  )
}
