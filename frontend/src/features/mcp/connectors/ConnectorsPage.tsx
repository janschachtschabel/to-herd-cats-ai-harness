import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { AiAdminTabs } from '@/features/ai/AiAdminTabs'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { useConnectors } from '../connectorQueries'
import { ClientsSection } from './ClientsSection'
import { ConnectorCard } from './ConnectorCard'
import { ConnectorDialog } from './ConnectorDialog'

/** The shared connectors (`ai.manage`): the organisation's stored access to external
 *  servers (a token, a header key, or OAuth), and the OAuth apps they sign in with. */
export function ConnectorsPage() {
  const { t } = useTranslation()
  const connectors = useConnectors('shared')
  const [creating, setCreating] = useState(false)
  const add = (
    <Button onClick={() => setCreating(true)}>
      <Plus aria-hidden />
      {t('mcp.connectors.create.open')}
    </Button>
  )
  return (
    <div>
      <PageHeader
        title={t('ai.title')}
        description={t('mcp.connectors.description')}
        actions={add}
      />
      <AiAdminTabs />
      <div className="flex flex-col gap-8">
        <section aria-labelledby="shared-connectors" className="flex flex-col gap-3">
          <h2 id="shared-connectors" className="text-base font-semibold">
            {t('mcp.connectors.title')}
          </h2>
          {connectors.isPending ? (
            <LoadingState rows={2} />
          ) : connectors.isError ? (
            <ErrorState error={connectors.error} onRetry={() => void connectors.refetch()} />
          ) : connectors.items.length === 0 ? (
            <EmptyState text={t('mcp.connectors.empty')}>{add}</EmptyState>
          ) : (
            <ul className="flex flex-col gap-3" aria-label={t('mcp.connectors.listLabel')}>
              {connectors.items.map((connector) => (
                <li key={connector.id}>
                  <ConnectorCard connector={connector} scope="shared" />
                </li>
              ))}
            </ul>
          )}
          <LoadMore
            hasMore={connectors.hasMore}
            loading={connectors.loadingMore}
            onLoad={connectors.loadMore}
          />
        </section>
        <ClientsSection />
      </div>
      <ConnectorDialog open={creating} scope="shared" onOpenChange={setCreating} />
    </div>
  )
}
