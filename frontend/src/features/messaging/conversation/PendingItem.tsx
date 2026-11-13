import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/queries'
import { errorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'
import { MessageMarkdown } from '../MessageMarkdown'
import type { PendingMessage } from './pending'
import { useSendMessage } from './queries'

/** One's own message before the server has it: "sending", or failed with "send again"
 *  (same client key, so it is never posted twice) and "discard". */
export function PendingItem({ pending }: { pending: PendingMessage }) {
  const { t } = useTranslation()
  const me = useMe()
  const { retry, discard } = useSendMessage(pending.conversationId, pending.parentId)
  const failed = pending.status === 'failed'
  return (
    <article
      aria-label={t('messaging.message.label', { author: me?.user.name ?? '' })}
      aria-busy={!failed}
      data-status={pending.status}
      className={cn('rounded-md px-2 py-1.5', failed && 'bg-destructive/5')}
    >
      <header className="flex items-baseline gap-2">
        <span className="text-sm font-semibold">{me?.user.name}</span>
        {!failed && (
          <span className="text-xs text-muted-foreground">{t('messaging.pending.sending')}</span>
        )}
      </header>
      <div className={cn(!failed && 'opacity-60')}>
        <MessageMarkdown markdown={pending.body} meId={me?.user.id} />
      </div>
      {failed && (
        <div role="alert" className="mt-1 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-destructive">
            {t('messaging.pending.failed', { reason: errorMessage(t, pending.error) })}
          </span>
          <Button size="xs" variant="outline" onClick={() => void retry(pending.clientId)}>
            {t('messaging.pending.retry')}
          </Button>
          <Button size="xs" variant="ghost" onClick={() => discard(pending.clientId)}>
            {t('messaging.pending.discard')}
          </Button>
        </div>
      )}
    </article>
  )
}
