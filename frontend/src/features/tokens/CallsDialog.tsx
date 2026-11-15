import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { formatDateTime } from '@/lib/format'
import { useTokenCalls, type CallsOwner, type Token } from './queries'

const OUTCOME_VARIANT = {
  ok: 'secondary',
  refused: 'outline',
  invalid: 'outline',
  failed: 'destructive',
} as const

/** A token's recent calls through `/mcp`: which tool, with what outcome, how long, when
 *  (never arguments or results: they are not stored). */
export function CallsDialog({
  token,
  owner,
  onClose,
}: {
  token: Token | null
  owner: CallsOwner
  onClose: () => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={token !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{t('tokens.calls.open', { name: token?.name ?? '' })}</DialogTitle>
          <DialogDescription>{t('tokens.calls.hint')}</DialogDescription>
        </DialogHeader>
        {token && <CallList owner={owner} tokenId={token.id} />}
      </DialogContent>
    </Dialog>
  )
}

function CallList({ owner, tokenId }: { owner: CallsOwner; tokenId: string }) {
  const { t, i18n } = useTranslation()
  const calls = useTokenCalls(owner, tokenId)
  if (calls.isPending) return <LoadingState rows={3} />
  if (calls.isError) return <ErrorState error={calls.error} onRetry={() => void calls.refetch()} />
  if (calls.items.length === 0) return <EmptyState text={t('tokens.calls.empty')} />
  return (
    <div className="min-w-0">
      <ul aria-label={t('tokens.calls.listLabel')} className="divide-y text-sm">
        {calls.items.map((call) => (
          <li key={call.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <span className="font-mono text-xs break-all">{call.tool}</span>
            <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant={OUTCOME_VARIANT[call.outcome]}>
                {t(`tokens.outcomes.${call.outcome}`)}
              </Badge>
              <span>{t('tokens.calls.duration', { ms: call.duration_ms })}</span>
              <time dateTime={call.created_at}>
                {formatDateTime(call.created_at, i18n.language)}
              </time>
            </span>
          </li>
        ))}
      </ul>
      <LoadMore hasMore={calls.hasMore} loading={calls.loadingMore} onLoad={calls.loadMore} />
    </div>
  )
}
