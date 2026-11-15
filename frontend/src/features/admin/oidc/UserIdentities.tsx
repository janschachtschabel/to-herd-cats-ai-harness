import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { SaveError } from '@/features/shared/forms'
import { ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { formatDateTime } from '@/lib/format'
import { useUnlinkUserIdentity, useUserIdentities } from './queries'

/** A person's linked sign-in accounts, for an admin with `user.manage`: see and unlink.
 *  The server refuses what the admin may not do (an owner's, the last way in). */
export function UserIdentities({ userId }: { userId: string }) {
  const { t, i18n } = useTranslation()
  const identities = useUserIdentities(userId)
  const unlink = useUnlinkUserIdentity(userId)
  return (
    <section className="flex flex-col gap-2 border-t pt-4" aria-labelledby="user-identities">
      <h3 id="user-identities" className="text-sm font-medium">
        {t('oidcAdmin.userIdentities.title')}
      </h3>
      {identities.isPending ? (
        <LoadingState />
      ) : identities.isError ? (
        <ErrorState error={identities.error} onRetry={() => void identities.refetch()} />
      ) : identities.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('oidcAdmin.userIdentities.empty')}</p>
      ) : (
        <ul className="flex flex-col divide-y rounded-md border">
          {identities.items.map((identity) => (
            <li key={identity.id} className="flex items-center justify-between gap-3 p-2 ps-3">
              <div className="min-w-0 text-sm">
                <div className="font-medium">{identity.provider_name}</div>
                <div className="text-xs text-muted-foreground">
                  {t('profile.identities.linkedAt', {
                    date: formatDateTime(identity.created_at, i18n.language),
                  })}
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={unlink.isPending}
                aria-label={t('oidcAdmin.userIdentities.unlinkNamed', {
                  name: identity.provider_name,
                })}
                onClick={() => unlink.mutate(identity.id)}
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
      <SaveError error={unlink.error} />
    </section>
  )
}
