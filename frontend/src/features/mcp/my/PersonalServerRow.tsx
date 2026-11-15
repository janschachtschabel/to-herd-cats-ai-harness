import { KeyRound, Link2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { SaveError } from '@/features/shared/forms'
import { useCreateConnector } from '../connectorQueries'
import { ConnectorCard } from '../connectors/ConnectorCard'
import { ConnectorDialog } from '../connectors/ConnectorDialog'
import { useConnect } from '../connectors/useConnect'
import type { Connector, PersonalServer } from '../display'

/** A server that acts in my name and that I have not connected yet: connect with the
 *  server's OAuth app (a connector of mine is made, then the browser goes to the
 *  provider), or store a token of mine. */
function NotConnected({ server }: { server: PersonalServer }) {
  const { t } = useTranslation()
  const create = useCreateConnector('personal')
  const oauth = useConnect('personal')
  const [typing, setTyping] = useState(false)
  const clientId = server.oauth_client_id
  return (
    <article aria-label={server.name} className="flex flex-col gap-2 rounded-lg border p-4">
      <div>
        <h3 className="font-semibold break-words">{server.name}</h3>
        <p className="text-sm text-amber-700 dark:text-amber-400">{t('mcp.my.notConnected')}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {clientId ? (
          <Button
            size="sm"
            disabled={create.isPending || oauth.pending}
            onClick={() =>
              create.mutate(
                {
                  name: server.name,
                  auth_kind: 'oauth',
                  oauth_client_id: clientId,
                  mcp_server_id: server.id,
                },
                { onSuccess: (made) => oauth.connect(made.id) },
              )
            }
          >
            <Link2 aria-hidden />
            {t('mcp.my.connectNamed', { name: server.name })}
          </Button>
        ) : (
          <Button size="sm" onClick={() => setTyping(true)}>
            <KeyRound aria-hidden />
            {t('mcp.my.storeToken')}
          </Button>
        )}
      </div>
      {oauth.unsafe && (
        <p role="alert" className="text-sm text-destructive">
          {t('mcp.connectors.unsafeAddress')}
        </p>
      )}
      <SaveError error={create.error ?? oauth.error} />
      <ConnectorDialog
        open={typing}
        scope="personal"
        server={{ id: server.id, name: server.name }}
        onOpenChange={setTyping}
      />
    </article>
  )
}

/** One server that acts in my name: connected (its connector, to reconnect, replace
 *  or remove) or not yet. */
export function PersonalServerRow({
  server,
  connector,
}: {
  server: PersonalServer
  connector: Connector | undefined
}) {
  if (!connector) return <NotConnected server={server} />
  return <ConnectorCard connector={connector} scope="personal" title={server.name} />
}
