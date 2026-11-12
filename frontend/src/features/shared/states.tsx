import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { errorDetails, errorMessage } from '@/lib/errors'

export function LoadingState({ rows = 4 }: { rows?: number }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-2" role="status" aria-label={t('states.loading')}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  )
}

export function EmptyState({ text, children }: { text: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
      <p>{text}</p>
      {children}
    </div>
  )
}

/** The backend's message and trace id, for whoever reports the problem. */
export function ErrorSmallPrint({ error }: { error: unknown }) {
  const { t } = useTranslation()
  const details = errorDetails(error)
  if (!details) return null
  return (
    <p className="mt-1 font-mono text-xs break-all text-muted-foreground">
      {details.message}
      {details.traceId && <> · {t('states.traceId', { traceId: details.traceId })}</>}
    </p>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useTranslation()
  return (
    <Alert variant="destructive">
      <AlertDescription className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-medium text-destructive">{errorMessage(t, error)}</p>
          <ErrorSmallPrint error={error} />
        </div>
        {onRetry && (
          <Button size="sm" variant="outline" onClick={onRetry}>
            {t('actions.retry')}
          </Button>
        )}
      </AlertDescription>
    </Alert>
  )
}

export function PageHeader({
  title,
  description,
  actions,
  children,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  children?: ReactNode
}) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        {children}
      </div>
      {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
    </header>
  )
}

/** "Mehr laden" under a paged list; nothing once the last page is in. */
export function LoadMore({
  hasMore,
  loading,
  onLoad,
}: {
  hasMore: boolean
  loading: boolean
  onLoad: () => void
}) {
  const { t } = useTranslation()
  if (!hasMore) return null
  return (
    <div className="mt-4 flex justify-center">
      <Button variant="outline" onClick={onLoad} disabled={loading}>
        {loading ? t('states.loadingMore') : t('actions.loadMore')}
      </Button>
    </div>
  )
}
