import { RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import type { Conversation } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { useStartAfresh } from './queries'

/** "Neu beginnen" in her DM alone with an agent (module review M8 3, H2): after it the
 *  agent's runs read nothing from before, so the personal mark of what came before
 *  ends for them. Asks first and says what it does; the server cancels open runs. */
export function FreshStartButton({
  conversation,
  agentName,
}: {
  conversation: Conversation
  agentName: string
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const start = useStartAfresh(conversation.id)
  return (
    <>
      <Button variant="outline" size="sm" className="ml-auto" onClick={() => setOpen(true)}>
        <RotateCcw aria-hidden />
        {t('agents.freshStart.action')}
      </Button>
      <ConfirmDialog
        open={open}
        title={t('agents.freshStart.title')}
        text={t('agents.freshStart.text', { agent: agentName })}
        confirmLabel={t('agents.freshStart.action')}
        pending={start.isPending}
        error={start.error}
        onConfirm={() => start.mutate(conversation.version, { onSuccess: () => setOpen(false) })}
        onOpenChange={(next) => {
          setOpen(next)
          if (!next) start.reset()
        }}
      />
    </>
  )
}

/** Where she started afresh, in the conversation's history: what is above it the
 *  agent no longer sees. */
export function FreshStartMarker({ at, agentName }: { at: string; agentName: string }) {
  const { t, i18n } = useTranslation()
  const title = t('agents.freshStart.marker', { when: formatDateTime(at, i18n.language) })
  return (
    <div
      role="separator"
      aria-label={title}
      className="my-2 flex items-center gap-3 text-xs text-sky-800 dark:text-sky-200"
    >
      <span className="h-px flex-1 bg-sky-300 dark:bg-sky-500/40" aria-hidden />
      <span className="text-center">
        <span className="font-semibold">{title}</span>
        <span className="block text-muted-foreground">
          {t('agents.freshStart.markerText', { agent: agentName })}
        </span>
      </span>
      <span className="h-px flex-1 bg-sky-300 dark:bg-sky-500/40" aria-hidden />
    </div>
  )
}
