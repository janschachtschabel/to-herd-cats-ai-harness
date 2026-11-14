import { KeyRound, Pencil, PlugZap, RefreshCw, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { SaveError } from '@/features/shared/forms'
import { cn } from '@/lib/utils'
import { checkTone, type Connection } from '../display'
import {
  useDeleteConnection,
  useFetchModels,
  useTestConnection,
  useUpdateConnection,
} from '../queries'

const TONES = {
  ok: 'text-emerald-700 dark:text-emerald-400',
  refused: 'text-amber-700 dark:text-amber-400',
  failed: 'text-destructive',
} as const

/** One connection: what it is, whether a key is stored, and what one can do with it. */
export function ConnectionCard({
  connection,
  onEdit,
}: {
  connection: Connection
  onEdit: () => void
}) {
  const { t, i18n } = useTranslation()
  const test = useTestConnection(connection.id)
  const toggle = useUpdateConnection(connection.id)
  const models = useFetchModels(connection.id)
  const remove = useDeleteConnection()
  const [confirming, setConfirming] = useState(false)
  const result = test.data
  const failure = toggle.error ?? models.error ?? test.error

  return (
    <article
      aria-label={connection.name}
      className={cn('rounded-lg border p-4', !connection.enabled && 'bg-muted/40')}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-semibold break-words">{connection.name}</h2>
          <p className="text-xs break-all text-muted-foreground">{connection.base_url}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline">{t(`ai.kinds.${connection.kind}`)}</Badge>
          <Badge variant="outline">{t(`ai.locations.${connection.data_location}`)}</Badge>
          <Badge variant="outline">{t(`ai.purposes.${connection.purpose}`)}</Badge>
          <Badge variant={connection.enabled ? 'secondary' : 'destructive'}>
            {connection.enabled ? t('ai.connections.on') : t('ai.connections.off')}
          </Badge>
        </div>
      </div>
      <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
        <dt className="text-muted-foreground">{t('ai.connections.fields.models')}</dt>
        <dd className="break-words">
          {connection.models.length === 0
            ? t('ai.connections.noModels')
            : connection.models.join(', ')}
        </dd>
        <dt className="text-muted-foreground">{t('ai.connections.fields.secret')}</dt>
        <dd className="inline-flex items-center gap-1">
          <KeyRound className="size-3.5 text-muted-foreground" aria-hidden />
          {connection.secret.set
            ? t(`ai.connections.secretKinds.${connection.secret.kind ?? 'enc'}`)
            : t('ai.connections.secretMissing')}
        </dd>
      </dl>
      {result && (
        <p role="status" className={cn('mt-3 text-sm', TONES[checkTone(result.status)])}>
          {t(`ai.check.${result.status}`, {
            model: result.model ?? '',
            ms: result.duration_ms.toLocaleString(i18n.language),
          })}
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={test.isPending}
          onClick={() => test.mutate(null)}
        >
          <PlugZap aria-hidden />
          {test.isPending ? t('ai.connections.testing') : t('ai.connections.test')}
        </Button>
        <Button size="sm" variant="outline" onClick={onEdit}>
          <Pencil aria-hidden />
          {t('actions.edit')}
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={toggle.isPending}
          onClick={() =>
            toggle.mutate({ enabled: !connection.enabled, version: connection.version })
          }
        >
          {connection.enabled ? t('ai.connections.disable') : t('ai.connections.enable')}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={models.isPending}
          onClick={() => models.mutate(connection.version)}
        >
          <RefreshCw aria-hidden />
          {t('ai.connections.fetchModels')}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label={t('ai.connections.deleteNamed', { name: connection.name })}
          onClick={() => setConfirming(true)}
        >
          <Trash2 aria-hidden />
        </Button>
      </div>
      {failure ? (
        <div className="mt-3">
          <SaveError error={failure} />
        </div>
      ) : null}
      <ConfirmDialog
        open={confirming}
        title={t('ai.connections.deleteTitle')}
        text={t('ai.connections.deleteText', { name: connection.name })}
        confirmLabel={t('actions.delete')}
        destructive
        pending={remove.isPending}
        error={remove.error}
        onOpenChange={setConfirming}
        onConfirm={() =>
          remove.mutate(
            { id: connection.id, version: connection.version },
            { onSuccess: () => setConfirming(false) },
          )
        }
      />
    </article>
  )
}
