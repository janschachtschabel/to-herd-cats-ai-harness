import { CircleAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { MessageTime } from '@/features/messaging/conversation/MessageTime'
import type { Message } from '@/lib/api'
import { stopText } from './display'

/** An agent's run that stopped without an answer: why, in words (the reason comes
 *  as `system.new.value`, never as text from the provider). */
export function RunStoppedNotice({ message }: { message: Message }) {
  const { t } = useTranslation()
  const reason = message.system?.new?.value ?? null
  return (
    <div
      data-kind="run-stopped"
      className="my-1 flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100"
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p className="min-w-0 flex-1">
        <span className="font-medium">{t('agents.stop.title')}</span> {stopText(t, reason)}
      </p>
      <MessageTime iso={message.created_at} />
    </div>
  )
}
