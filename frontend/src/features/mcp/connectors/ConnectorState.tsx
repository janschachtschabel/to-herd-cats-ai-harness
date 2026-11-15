import { CircleCheck, CircleDashed, KeyRound } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { connectorState, type Connector } from '../display'

/** What a connector holds, in words: connected or not (OAuth), or a key stored
 *  encrypted or named as an environment variable. Never the secret. */
export function ConnectorStateText({
  connector,
  className,
}: {
  connector: Pick<Connector, 'auth_kind' | 'has_secret' | 'secret_kind'>
  className?: string
}) {
  const { t } = useTranslation()
  const state = connectorState(connector)
  const Icon =
    state === 'connected' ? CircleCheck : state === 'disconnected' ? CircleDashed : KeyRound
  return (
    <span
      data-connector-state={state}
      className={cn(
        'inline-flex items-center gap-1 text-sm',
        state === 'connected' && 'text-emerald-700 dark:text-emerald-400',
        state === 'disconnected' && 'text-amber-700 dark:text-amber-400',
        className,
      )}
    >
      <Icon className="size-3.5 shrink-0" aria-hidden />
      {t(`mcp.connectors.states.${state}`)}
    </span>
  )
}
