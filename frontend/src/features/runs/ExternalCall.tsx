import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { TimelineItem } from './timeline'

type ToolItem = Extract<TimelineItem, { kind: 'tool' }>

/** An external call's title: "Server · tool", marked as external. */
export function ExternalTitle({ external }: { external: NonNullable<ToolItem['external']> }) {
  const { t } = useTranslation()
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span>{t('runs.external.title', { server: external.server, tool: external.tool })}</span>
      <Badge variant="outline">{t('runs.external.badge')}</Badge>
    </span>
  )
}

const WARN = new Set([
  'unknown',
  'not_connected',
  'unavailable',
  'credential_unavailable',
  'policy',
])

/** What became of an external call, in words: still being sent, its answer never
 *  recorded (it was not sent again), or why it was not made or failed. */
export function ExternalOutcomeNote({ outcome }: { outcome: ToolItem['outcome'] }) {
  const { t } = useTranslation()
  if (!outcome) return null
  return (
    <p
      className={cn(
        'mt-1 text-sm',
        outcome === 'sending' && 'text-muted-foreground',
        WARN.has(outcome) && 'text-amber-800 dark:text-amber-300',
        (outcome === 'failed' || outcome === 'error') && 'text-destructive',
      )}
    >
      {t(`runs.external.outcomes.${outcome}`)}
    </p>
  )
}
