import { useTranslation } from 'react-i18next'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { useConnectors, useMyServers } from '../connectorQueries'
import { ConnectorCard } from '../connectors/ConnectorCard'
import { PersonalServerRow } from './PersonalServerRow'

/** "My connections" (`ai.use`): the external servers that act in my name, each with
 *  my own access (OAuth or a token of mine). Agents I ask use it for me; no one else
 *  sees or uses it, admins included. */
export function MyConnectionsPage() {
  const { t } = useTranslation()
  const servers = useMyServers()
  const connectors = useConnectors('personal')
  const pending = servers.isPending || connectors.isPending
  const error = servers.error ?? connectors.error
  const listed = new Set(servers.items.map((server) => server.id))
  const others = connectors.items.filter(
    (connector) => connector.mcp_server_id === null || !listed.has(connector.mcp_server_id),
  )
  return (
    <div className="max-w-3xl">
      <PageHeader title={t('mcp.my.title')} description={t('mcp.my.description')} />
      {pending ? (
        <LoadingState rows={2} />
      ) : error ? (
        <ErrorState
          error={error}
          onRetry={() => {
            void servers.refetch()
            void connectors.refetch()
          }}
        />
      ) : (
        <div className="flex flex-col gap-6">
          {servers.items.length === 0 ? (
            <EmptyState text={t('mcp.my.empty')} />
          ) : (
            <ul className="flex flex-col gap-3" aria-label={t('mcp.my.listLabel')}>
              {servers.items.map((server) => (
                <li key={server.id}>
                  <PersonalServerRow
                    server={server}
                    connector={connectors.items.find((c) => c.mcp_server_id === server.id)}
                  />
                </li>
              ))}
            </ul>
          )}
          <LoadMore
            hasMore={servers.hasMore}
            loading={servers.loadingMore}
            onLoad={servers.loadMore}
          />
          {others.length > 0 && (
            <section aria-labelledby="my-other-connectors" className="flex flex-col gap-3">
              <div>
                <h2 id="my-other-connectors" className="text-base font-semibold">
                  {t('mcp.my.othersTitle')}
                </h2>
                <p className="text-sm text-muted-foreground">{t('mcp.my.othersHint')}</p>
              </div>
              <ul className="flex flex-col gap-3">
                {others.map((connector) => (
                  <li key={connector.id}>
                    <ConnectorCard connector={connector} scope="personal" />
                  </li>
                ))}
              </ul>
            </section>
          )}
          <LoadMore
            hasMore={connectors.hasMore}
            loading={connectors.loadingMore}
            onLoad={connectors.loadMore}
          />
        </div>
      )}
    </div>
  )
}
