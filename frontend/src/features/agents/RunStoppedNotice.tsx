import { CircleAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { MessageTime } from '@/features/messaging/conversation/MessageTime'
import { VisibleRunLink } from '@/features/runs/RunBits'
import type { Message } from '@/lib/api'
import { AgentBadge } from './AgentBadge'
import { noRunText, RUN_REFUSED, stopText } from './display'

/** A run notice of a conversation or thread, in words (the reason comes as
 *  `system.new.value`, never as text from the provider): a run that stopped without
 *  an answer (`run.stopped`), or one that could not start or hand over
 *  (`run.refused`, its code from the run refusals); one that held back an answer
 *  for what the asking person read with her own connector says so. The agent is named where the
 *  server names it, with the AI mark; the run is linked for those who may see it. */
export function RunStoppedNotice({ message }: { message: Message }) {
  const { t } = useTranslation()
  const entry = message.system
  const reason = entry?.new?.value ?? null
  const agent = entry?.actor?.type === 'agent' ? entry.actor : null
  const name = agent?.name ?? t('agents.stop.someAgent')
  const refused = entry?.key === RUN_REFUSED
  return (
    <div
      data-kind={refused ? 'run-refused' : 'run-stopped'}
      className="my-1 flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100"
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        {refused ? (
          <p>
            {t(
              reason === 'run.handover_limit' ? 'agents.refused.handover' : 'agents.refused.start',
              {
                name,
                reason: noRunText(t, reason ?? ''),
              },
            )}
          </p>
        ) : (
          <p>
            <span className="font-medium">
              {agent ? t('agents.stop.titleNamed', { name }) : t('agents.stop.title')}
            </span>{' '}
            <span>{stopText(t, reason)}</span>
          </p>
        )}
        {!refused && entry?.stop_detail === 'personal_connector' && (
          <p className="mt-0.5">{t('runs.external.personalConnector')}</p>
        )}
        {entry?.run_id && <VisibleRunLink runId={entry.run_id} className="mt-1" />}
      </div>
      {agent && <AgentBadge />}
      <MessageTime iso={message.created_at} />
    </div>
  )
}
