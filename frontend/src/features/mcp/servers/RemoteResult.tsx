import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { remoteTone, TONE_CLASSES, type RefreshResult, type RemoteStatus } from '../display'

/** What a server answered, in words (never the server's own text). */
export function RemoteStatusText({
  status,
  className,
}: {
  status: RemoteStatus
  className?: string
}) {
  const { t } = useTranslation()
  return (
    <p role="status" className={cn('text-sm', TONE_CLASSES[remoteTone(status)], className)}>
      {t(`mcp.remote.${status}`)}
    </p>
  )
}

/** A connection test: the status, and on success how many tools and how fast. */
export function TestResult({
  status,
  tools,
  durationMs,
}: {
  status: RemoteStatus
  tools: number | null
  durationMs: number
}) {
  const { t, i18n } = useTranslation()
  if (status !== 'ok') return <RemoteStatusText status={status} />
  return (
    <p role="status" className={cn('text-sm', TONE_CLASSES.ok)}>
      {t('mcp.servers.testOk', {
        count: tools ?? 0,
        ms: durationMs.toLocaleString(i18n.language),
      })}
    </p>
  )
}

/** A refresh of the tool list: what came in new, changed or went missing. */
export function RefreshSummary({ result }: { result: RefreshResult }) {
  const { t } = useTranslation()
  if (result.status !== 'ok') return <RemoteStatusText status={result.status} />
  const parts = [
    result.new && t('mcp.refresh.new', { count: result.new }),
    result.changed && t('mcp.refresh.changed', { count: result.changed }),
    result.missing && t('mcp.refresh.missing', { count: result.missing }),
  ].filter(Boolean)
  return (
    <p role="status" className={cn('text-sm', TONE_CLASSES.ok)}>
      {parts.length === 0 ? t('mcp.refresh.unchanged') : parts.join(' · ')}
    </p>
  )
}
