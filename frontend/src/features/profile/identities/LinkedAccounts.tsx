import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ProviderIcon } from '@/features/auth/OidcButtons'
import { useSignInError } from '@/features/auth/signInError'
import { useSignInProviders } from '@/features/auth/queries'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { SaveError } from '@/features/shared/forms'
import { ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { formatDateTime } from '@/lib/format'
import { useMyIdentities, useStartLink, useUnlinkMine, type Identity } from './queries'

/** The person's accounts at sign-in providers: link one more, or unlink one. */
export function LinkedAccounts({ linked, linkError }: { linked?: string; linkError?: string }) {
  const { t, i18n } = useTranslation()
  const identities = useMyIdentities()
  const providers = useSignInProviders()
  const startLink = useStartLink()
  const unlink = useUnlinkMine()
  const [unlinking, setUnlinking] = useState<Identity | null>(null)
  const refused = useSignInError(linkError)
  const linkedName = providers.find((p) => p.key === linked)?.name ?? linked
  const linkedKeys = new Set(identities.items.map((i) => i.provider_key))
  const offered = providers.filter((p) => !linkedKeys.has(p.key))
  if (providers.length === 0 && identities.items.length === 0 && !identities.isPending) return null
  return (
    <section className="mt-8 flex flex-col gap-3 border-t pt-6" aria-labelledby="linked-accounts">
      <div>
        <h2 id="linked-accounts" className="text-base font-semibold">
          {t('profile.identities.title')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('profile.identities.description')}</p>
      </div>
      {linked && !refused && (
        <Alert>
          <AlertDescription>
            {t('profile.identities.linked', { name: linkedName })}
          </AlertDescription>
        </Alert>
      )}
      {refused && (
        <Alert variant="destructive">
          <AlertDescription>
            <p className="font-medium">{t('profile.identities.linkFailed')}</p>
            <p>{refused}</p>
          </AlertDescription>
        </Alert>
      )}
      {identities.isPending ? (
        <LoadingState />
      ) : identities.isError ? (
        <ErrorState error={identities.error} onRetry={() => void identities.refetch()} />
      ) : identities.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('profile.identities.empty')}</p>
      ) : (
        <ul className="flex flex-col divide-y rounded-md border">
          {identities.items.map((identity) => (
            <li key={identity.id} className="flex items-center justify-between gap-3 p-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 font-medium">
                  <ProviderIcon kind={identity.provider_kind} />
                  {identity.provider_name}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t('profile.identities.linkedAt', {
                    date: formatDateTime(identity.created_at, i18n.language),
                  })}
                  {identity.last_login_at && (
                    <>
                      {' · '}
                      {t('profile.identities.lastLogin', {
                        date: formatDateTime(identity.last_login_at, i18n.language),
                      })}
                    </>
                  )}
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                aria-label={t('profile.identities.unlinkNamed', { name: identity.provider_name })}
                onClick={() => {
                  unlink.reset()
                  setUnlinking(identity)
                }}
              >
                {t('profile.identities.unlink')}
              </Button>
            </li>
          ))}
        </ul>
      )}
      <LoadMore
        hasMore={identities.hasMore}
        loading={identities.loadingMore}
        onLoad={identities.loadMore}
      />
      {offered.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {offered.map((provider) => (
            <Button
              key={provider.key}
              variant="outline"
              disabled={startLink.isPending}
              onClick={() => startLink.mutate(provider.key)}
            >
              <ProviderIcon kind={provider.kind} />
              {startLink.isPending && startLink.variables === provider.key
                ? t('profile.identities.linking')
                : t('profile.identities.link', { name: provider.name })}
            </Button>
          ))}
        </div>
      )}
      <SaveError error={startLink.error} />
      <ConfirmDialog
        open={unlinking !== null}
        title={t('profile.identities.unlinkTitle')}
        text={t('profile.identities.unlinkText', { name: unlinking?.provider_name ?? '' })}
        confirmLabel={t('profile.identities.unlink')}
        destructive
        pending={unlink.isPending}
        error={unlink.error}
        onConfirm={() =>
          unlinking && unlink.mutate(unlinking.id, { onSuccess: () => setUnlinking(null) })
        }
        onOpenChange={(open) => !open && setUnlinking(null)}
      />
    </section>
  )
}
