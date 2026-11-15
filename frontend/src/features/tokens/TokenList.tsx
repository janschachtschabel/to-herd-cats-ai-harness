import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { useNow } from '@/lib/useNow'
import { CallsDialog } from './CallsDialog'
import { useRevokeToken, type CallsOwner, type Token } from './queries'
import { TokenRow } from './TokenRow'

interface PagedTokens<T> {
  items: T[]
  isPending: boolean
  isError: boolean
  error: unknown
  refetch: () => unknown
  hasMore: boolean
  loadingMore: boolean
  loadMore: () => void
}

/** Tokens as a list (newest first, paged): each with its calls and, while it works,
 *  revoking it after a confirmation. Loading, empty and error states included. */
export function TokenList<T extends Token>({
  tokens,
  owner,
  spaceNames,
  emptyText,
  label,
  ownerOf,
}: {
  tokens: PagedTokens<T>
  owner: CallsOwner
  spaceNames: ReadonlyMap<string, string>
  emptyText: string
  label: string
  ownerOf?: (token: T) => ReactNode
}) {
  const { t } = useTranslation()
  const now = new Date(useNow(60_000))
  const revoke = useRevokeToken(owner)
  const [calls, setCalls] = useState<T | null>(null)
  const [revoking, setRevoking] = useState<T | null>(null)

  if (tokens.isPending) return <LoadingState rows={2} />
  if (tokens.isError) {
    return <ErrorState error={tokens.error} onRetry={() => void tokens.refetch()} />
  }
  if (tokens.items.length === 0) return <EmptyState text={emptyText} />
  return (
    <>
      <ul aria-label={label} className="flex flex-col gap-3">
        {tokens.items.map((token) => (
          <li key={token.id}>
            <TokenRow
              token={token}
              now={now}
              spaceNames={spaceNames}
              owner={ownerOf?.(token)}
              onCalls={() => setCalls(token)}
              onRevoke={() => {
                revoke.reset()
                setRevoking(token)
              }}
            />
          </li>
        ))}
      </ul>
      <LoadMore hasMore={tokens.hasMore} loading={tokens.loadingMore} onLoad={tokens.loadMore} />
      <CallsDialog token={calls} owner={owner} onClose={() => setCalls(null)} />
      <ConfirmDialog
        open={revoking !== null}
        title={t('tokens.revoke.title')}
        text={t('tokens.revoke.text', { name: revoking?.name ?? '' })}
        confirmLabel={t('tokens.revoke.short')}
        destructive
        pending={revoke.isPending}
        error={revoke.error}
        onOpenChange={(open) => !open && setRevoking(null)}
        onConfirm={() =>
          revoking && revoke.mutate(revoking.id, { onSuccess: () => setRevoking(null) })
        }
      />
    </>
  )
}
