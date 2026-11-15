import { History, KeyRound, Trash2 } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/lib/format'
import { scopeNames, tokenState, type TokenState } from './display'
import type { Token } from './queries'

const STATE_VARIANT = { active: 'secondary', expired: 'outline', revoked: 'destructive' } as const

/** One token: its name and state, what it may (mode, spaces), its dates; its calls,
 *  and revoking it while it still works. `owner`: whose it is (the admins' list). */
export function TokenRow({
  token,
  now,
  spaceNames,
  owner,
  onCalls,
  onRevoke,
}: {
  token: Token
  now: Date
  spaceNames: ReadonlyMap<string, string>
  owner?: ReactNode
  onCalls: () => void
  onRevoke: () => void
}) {
  const { t, i18n } = useTranslation()
  const state: TokenState = tokenState(token, now)
  const when = (value: string) => formatDateTime(value, i18n.language)
  return (
    <article aria-label={token.name} className="flex flex-col gap-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="flex min-w-0 items-center gap-2 font-semibold break-words">
          <KeyRound className="size-4 shrink-0 text-muted-foreground" aria-hidden />
          {token.name}
        </h2>
        <span className="flex flex-wrap gap-1">
          <Badge variant="outline">{t(`tokens.modes.${token.mode}`)}</Badge>
          <Badge variant={STATE_VARIANT[state]}>{t(`tokens.states.${state}`)}</Badge>
        </span>
      </div>
      {owner && <p className="text-sm text-muted-foreground">{owner}</p>}
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <Fact label={t('tokens.facts.scope')}>
          <Scope spaceIds={token.space_ids} names={spaceNames} />
        </Fact>
        <Fact label={t('tokens.facts.lastUsed')}>
          {token.last_used_at ? when(token.last_used_at) : t('tokens.facts.never')}
        </Fact>
        <Fact label={t('tokens.facts.created')}>{when(token.created_at)}</Fact>
        <Fact label={token.revoked_at ? t('tokens.facts.revoked') : t('tokens.facts.expires')}>
          {when(token.revoked_at ?? token.expires_at)}
        </Fact>
      </dl>
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          aria-label={t('tokens.calls.open', { name: token.name })}
          onClick={onCalls}
        >
          <History aria-hidden />
          {t('tokens.calls.short')}
        </Button>
        {state !== 'revoked' && (
          <Button
            size="sm"
            variant="outline"
            aria-label={t('tokens.revoke.named', { name: token.name })}
            onClick={onRevoke}
          >
            <Trash2 aria-hidden />
            {t('tokens.revoke.short')}
          </Button>
        )}
      </div>
    </article>
  )
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="break-words">{children}</dd>
    </div>
  )
}

function Scope({
  spaceIds,
  names,
}: {
  spaceIds: readonly string[] | null
  names: ReadonlyMap<string, string>
}) {
  const { t } = useTranslation()
  const scope = scopeNames(spaceIds, names)
  if (scope.all) return <>{t('tokens.scope.all')}</>
  return (
    <span className="flex flex-wrap gap-1">
      {scope.named.map((name) => (
        <Badge key={name} variant="outline">
          {name}
        </Badge>
      ))}
      {scope.unnamed > 0 && (
        <span className="text-muted-foreground">
          {t('tokens.scope.unnamed', { count: scope.unnamed })}
        </span>
      )}
    </span>
  )
}
