import { Link2, Unlink } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { SaveError } from '@/features/shared/forms'
import { useDisconnectConnector, type ConnectorScope } from '../connectorQueries'
import type { Connector } from '../display'
import { useConnect } from './useConnect'

/** Connect, reconnect or disconnect an OAuth connector. Connecting leaves the app for
 *  the provider's sign-in page; disconnecting drops the tokens here and tells the
 *  provider. */
export function OAuthButtons({
  connector,
  scope,
}: {
  connector: Connector
  scope: ConnectorScope
}) {
  const { t } = useTranslation()
  const { connect, pending, error, unsafe } = useConnect(scope)
  const disconnect = useDisconnectConnector(scope)
  const connected = connector.has_secret
  return (
    <>
      <Button
        size="sm"
        variant={connected ? 'outline' : 'default'}
        disabled={pending}
        onClick={() => connect(connector.id)}
      >
        <Link2 aria-hidden />
        {connected ? t('mcp.connectors.reconnect') : t('mcp.connectors.connect')}
      </Button>
      {connected && (
        <Button
          size="sm"
          variant="outline"
          disabled={disconnect.isPending}
          onClick={() => disconnect.mutate({ id: connector.id, version: connector.version })}
        >
          <Unlink aria-hidden />
          {t('mcp.connectors.disconnect')}
        </Button>
      )}
      {unsafe && (
        <p role="alert" className="w-full text-sm text-destructive">
          {t('mcp.connectors.unsafeAddress')}
        </p>
      )}
      {(error ?? disconnect.error) ? (
        <div className="w-full">
          <SaveError error={error ?? disconnect.error} />
        </div>
      ) : null}
    </>
  )
}
