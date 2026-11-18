import { KeyRound, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { useDeleteClient, useOAuthClients } from '../connectorQueries'
import type { OAuthClient } from '../display'
import { ClientDialog } from './ClientDialog'

function ClientCard({ client }: { client: OAuthClient }) {
  const { t } = useTranslation()
  const remove = useDeleteClient()
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  return (
    <article aria-label={client.name} className="flex flex-col gap-2 rounded-lg border p-4">
      <div>
        <h3 className="font-semibold break-words">{client.name}</h3>
        <p className="text-xs break-all text-muted-foreground">{client.authorization_endpoint}</p>
      </div>
      <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
        <dt className="text-muted-foreground">{t('mcp.clients.fields.clientId')}</dt>
        <dd className="font-mono text-xs break-all">{client.client_id}</dd>
        <dt className="text-muted-foreground">{t('mcp.clients.fields.secret')}</dt>
        <dd className="inline-flex items-center gap-1">
          <KeyRound className="size-3.5 text-muted-foreground" aria-hidden />
          {client.has_client_secret
            ? t(`mcp.clients.secretKinds.${client.client_secret_kind ?? 'enc'}`)
            : t('mcp.clients.secretNone')}
        </dd>
        <dt className="text-muted-foreground">{t('mcp.clients.fields.callback')}</dt>
        <dd className="font-mono text-xs break-all">
          {client.callback_url ?? (
            <span className="font-sans text-muted-foreground">
              {t('mcp.clients.callbackMissing')}
            </span>
          )}
        </dd>
        {client.scopes && (
          <>
            <dt className="text-muted-foreground">{t('mcp.clients.fields.scopes')}</dt>
            <dd className="font-mono text-xs break-all">{client.scopes}</dd>
          </>
        )}
      </dl>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
          <Pencil aria-hidden />
          {t('actions.edit')}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label={t('mcp.clients.deleteNamed', { name: client.name })}
          onClick={() => setConfirming(true)}
        >
          <Trash2 aria-hidden />
        </Button>
      </div>
      <ClientDialog key={client.version} open={editing} client={client} onOpenChange={setEditing} />
      <ConfirmDialog
        open={confirming}
        title={t('mcp.clients.deleteTitle')}
        text={t('mcp.clients.deleteText', { name: client.name })}
        confirmLabel={t('actions.delete')}
        destructive
        pending={remove.isPending}
        error={remove.error}
        onOpenChange={setConfirming}
        onConfirm={() =>
          remove.mutate(
            { id: client.id, version: client.version },
            { onSuccess: () => setConfirming(false) },
          )
        }
      />
    </article>
  )
}

/** The OAuth apps registered with providers: what OAuth connectors and personal
 *  servers sign in with. The catalogue registers them by itself. */
export function ClientsSection() {
  const { t } = useTranslation()
  const clients = useOAuthClients()
  const [creating, setCreating] = useState(false)
  return (
    <section aria-labelledby="oauth-clients" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id="oauth-clients" className="text-base font-semibold">
            {t('mcp.clients.title')}
          </h2>
          <p className="text-sm text-muted-foreground">{t('mcp.clients.hint')}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => setCreating(true)}>
          <Plus aria-hidden />
          {t('mcp.clients.create.open')}
        </Button>
      </div>
      {clients.isPending ? (
        <LoadingState rows={2} />
      ) : clients.isError ? (
        <ErrorState error={clients.error} onRetry={() => void clients.refetch()} />
      ) : clients.items.length === 0 ? (
        <EmptyState text={t('mcp.clients.empty')} />
      ) : (
        <ul className="flex flex-col gap-3" aria-label={t('mcp.clients.listLabel')}>
          {clients.items.map((client) => (
            <li key={client.id}>
              <ClientCard client={client} />
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={clients.hasMore} loading={clients.loadingMore} onLoad={clients.loadMore} />
      <ClientDialog open={creating} onOpenChange={setCreating} />
    </section>
  )
}
