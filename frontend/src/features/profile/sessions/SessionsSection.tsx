import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { SaveError } from '@/features/shared/forms'
import { ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { formatDateTime } from '@/lib/format'
import { useEndSession, useMySessions, useSignOutOthers } from './queries'

/** Where the person is signed in: each running session with its device and times; she
 *  ends one, or every one but this browser's (ASVS V7.5.2). */
export function SessionsSection() {
  const { t, i18n } = useTranslation()
  const sessions = useMySessions()
  const end = useEndSession()
  const others = useSignOutOthers()
  const [asking, setAsking] = useState(false)
  const hasOthers = sessions.items.some((s) => !s.current) || sessions.hasMore
  return (
    <section className="mt-8 flex flex-col gap-3 border-t pt-6" aria-labelledby="own-sessions">
      <div>
        <h2 id="own-sessions" className="text-base font-semibold">
          {t('security.sessions.title')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('security.sessions.description')}</p>
      </div>
      {sessions.isPending ? (
        <LoadingState />
      ) : sessions.isError ? (
        <ErrorState error={sessions.error} onRetry={() => void sessions.refetch()} />
      ) : (
        <ul className="flex flex-col divide-y rounded-md border">
          {sessions.items.map((item) => {
            const device = item.device ?? t('security.sessions.unknownDevice')
            return (
              <li key={item.id} className="flex items-center justify-between gap-3 p-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 font-medium">
                    {device}
                    {item.current && (
                      <Badge variant="secondary">{t('security.sessions.current')}</Badge>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {t('security.sessions.signedInAt', {
                      date: formatDateTime(item.signed_in_at, i18n.language),
                    })}
                    {' · '}
                    {t('security.sessions.lastUsed', {
                      date: formatDateTime(item.last_used_at, i18n.language),
                    })}
                  </div>
                </div>
                {!item.current && (
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={t('security.sessions.endNamed', { device })}
                    disabled={end.isPending && end.variables === item.id}
                    onClick={() => end.mutate(item.id)}
                  >
                    {t('security.sessions.end')}
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
      )}
      <LoadMore
        hasMore={sessions.hasMore}
        loading={sessions.loadingMore}
        onLoad={sessions.loadMore}
      />
      <SaveError error={end.error} />
      {hasOthers && (
        <div>
          <Button
            variant="outline"
            onClick={() => {
              others.reset()
              setAsking(true)
            }}
          >
            {t('security.sessions.endOthers')}
          </Button>
        </div>
      )}
      <ConfirmDialog
        open={asking}
        title={t('security.sessions.endOthersTitle')}
        text={t('security.sessions.endOthersText')}
        confirmLabel={t('security.sessions.endOthers')}
        destructive
        pending={others.isPending}
        error={others.error}
        onConfirm={() => others.mutate(undefined, { onSuccess: () => setAsking(false) })}
        onOpenChange={setAsking}
      />
    </section>
  )
}
