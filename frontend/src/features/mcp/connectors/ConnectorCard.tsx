import { Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { useDeleteConnector, type ConnectorScope } from '../connectorQueries'
import type { Connector } from '../display'
import { ConnectorDialog } from './ConnectorDialog'
import { ConnectorStateText } from './ConnectorState'
import { OAuthButtons } from './OAuthButtons'

/** One connector: its kind, what it holds (never the secret), and what one can do: an
 *  OAuth one is connected, reconnected or disconnected; a key is replaced; either is
 *  deleted (not while a server uses it: the API answers 409 `connector.in_use`). */
export function ConnectorCard({
  connector,
  scope,
  title,
}: {
  connector: Connector
  scope: ConnectorScope
  /** Shown instead of the connector's name (one's own: the server's name). */
  title?: string
}) {
  const { t } = useTranslation()
  const remove = useDeleteConnector(scope)
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const name = title ?? connector.name
  return (
    <article aria-label={name} className="flex flex-col gap-2 rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-semibold break-words">{name}</h3>
          <ConnectorStateText connector={connector} />
        </div>
        <span className="flex flex-wrap gap-1.5">
          <Badge variant="outline">{t(`mcp.connectors.kinds.${connector.auth_kind}`)}</Badge>
          {connector.header_name && (
            <Badge variant="outline" className="font-mono">
              {connector.header_name}
            </Badge>
          )}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {connector.auth_kind === 'oauth' ? (
          <OAuthButtons connector={connector} scope={scope} />
        ) : (
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
            <Pencil aria-hidden />
            {t('mcp.connectors.replaceKey')}
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          aria-label={t('mcp.connectors.deleteNamed', { name })}
          onClick={() => setConfirming(true)}
        >
          <Trash2 aria-hidden />
        </Button>
      </div>
      <ConnectorDialog
        key={connector.version}
        open={editing}
        scope={scope}
        connector={connector}
        onOpenChange={setEditing}
      />
      <ConfirmDialog
        open={confirming}
        title={t('mcp.connectors.deleteTitle')}
        text={t(`mcp.connectors.deleteText.${scope}`, { name })}
        confirmLabel={t('actions.delete')}
        destructive
        pending={remove.isPending}
        error={remove.error}
        onOpenChange={setConfirming}
        onConfirm={() =>
          remove.mutate(
            { id: connector.id, version: connector.version },
            { onSuccess: () => setConfirming(false) },
          )
        }
      />
    </article>
  )
}
