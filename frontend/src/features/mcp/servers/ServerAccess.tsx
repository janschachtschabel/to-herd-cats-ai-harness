import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { errorMessage } from '@/lib/errors'
import { useConnector } from '../connectorQueries'
import type { Server } from '../display'
import { ConnectorStateText } from '../connectors/ConnectorState'
import { OAuthButtons } from '../connectors/OAuthButtons'

/** Whose access the server uses: none; a shared connector (its state, and for OAuth
 *  connect/reconnect right here); or each person's own (they connect it under "My
 *  connections"). */
export function ServerAccess({ server }: { server: Server }) {
  const { t } = useTranslation()
  const connector = useConnector(server.connector_scope === 'shared' ? server.connector_id : null)
  return (
    <section aria-labelledby="server-access" className="rounded-lg border p-4">
      <h2 id="server-access" className="text-base font-semibold">
        {t('mcp.servers.accessTitle')}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        {t(`mcp.access.hints.${server.connector_scope}`)}
      </p>
      {server.connector_scope === 'shared' &&
        (connector.isPending ? (
          <p className="mt-2 text-sm text-muted-foreground">{t('states.loading')}</p>
        ) : connector.isError ? (
          <p role="alert" className="mt-2 text-sm text-destructive">
            {errorMessage(t, connector.error)}
          </p>
        ) : (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="font-medium">{connector.data.name}</span>
            <ConnectorStateText connector={connector.data} />
            {connector.data.auth_kind === 'oauth' && (
              <OAuthButtons connector={connector.data} scope="shared" />
            )}
          </div>
        ))}
      {server.connector_scope === 'personal' && (
        <p className="mt-2 text-sm">
          {server.oauth_client_id
            ? t('mcp.servers.personalWithOAuth')
            : t('mcp.servers.personalWithToken')}
        </p>
      )}
      <p className="mt-2 text-xs">
        <Link to="/admin/ai/connectors" className="font-medium underline underline-offset-2">
          {t('mcp.servers.toConnectors')}
        </Link>
      </p>
    </section>
  )
}
