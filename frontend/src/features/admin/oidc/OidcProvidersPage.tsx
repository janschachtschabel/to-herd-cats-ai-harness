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
import { ProviderCard } from './ProviderCard'
import { ProviderDialog } from './ProviderDialog'
import type { ProviderKind } from './providerForm'
import { useOidcProviders, type OidcProvider } from './queries'

/** Sign-in providers (`user.manage`): Google from its preset, any other OIDC provider,
 *  self-registration for allowed domains. */
export function OidcProvidersPage() {
  const { t } = useTranslation()
  const providers = useOidcProviders()
  const [creating, setCreating] = useState(false)
  // Kept after closing so the dialog does not change its title while it fades out.
  const [kind, setKind] = useState<ProviderKind>('google')
  const create = (next: ProviderKind) => {
    setKind(next)
    setCreating(true)
  }
  const [editing, setEditing] = useState<OidcProvider | null>(null)
  const hasGoogle = providers.items.some((provider) => provider.kind === 'google')

  const actions = (
    <>
      {!hasGoogle && (
        <Button onClick={() => create('google')}>
          <Plus aria-hidden />
          {t('oidcAdmin.addGoogle')}
        </Button>
      )}
      <Button variant={hasGoogle ? 'default' : 'outline'} onClick={() => create('generic')}>
        <Plus aria-hidden />
        {t('oidcAdmin.addGeneric')}
      </Button>
    </>
  )

  return (
    <div>
      <PageHeader
        title={t('oidcAdmin.title')}
        description={t('oidcAdmin.description')}
        actions={<div className="flex flex-wrap gap-2">{actions}</div>}
      />
      {providers.isPending ? (
        <LoadingState />
      ) : providers.isError ? (
        <ErrorState error={providers.error} onRetry={() => void providers.refetch()} />
      ) : providers.items.length === 0 ? (
        <EmptyState text={t('oidcAdmin.empty')} />
      ) : (
        <ul className="flex flex-col gap-3" aria-label={t('oidcAdmin.listLabel')}>
          {providers.items.map((provider) => (
            <li key={provider.id}>
              <ProviderCard provider={provider} onEdit={() => setEditing(provider)} />
            </li>
          ))}
        </ul>
      )}
      <LoadMore
        hasMore={providers.hasMore}
        loading={providers.loadingMore}
        onLoad={providers.loadMore}
      />
      <ProviderDialog key={kind} open={creating} kind={kind} onOpenChange={setCreating} />
      <ProviderDialog
        key={editing?.id ?? 'none'}
        open={editing !== null}
        provider={editing ?? undefined}
        onOpenChange={(open) => !open && setEditing(null)}
      />
    </div>
  )
}
