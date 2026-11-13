import type { UseQueryResult } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/features/shared/states'
import type { Conversation, SpaceRole } from '@/lib/api'
import { cn } from '@/lib/utils'
import { ConversationPane } from '../conversation/ConversationPane'

/**
 * The discussion of a page or a ticket (spec 6.2): comments and the grey timeline of
 * what happened to it, which can be hidden. Whoever sees the page or ticket sees it;
 * writing needs the same right as in the space's channels (the thread's `can_post`).
 */
export function DiscussionPanel({
  conversation,
  spaceRole,
  title,
  emptyText,
  composerLabel,
  thread: initialThread,
  highlight,
  onClose,
  className,
}: {
  conversation: UseQueryResult<Conversation>
  spaceRole: SpaceRole | null | undefined
  title: string
  emptyText: string
  composerLabel: string
  thread?: string
  highlight?: string
  /** Shown as a close button when given (a panel beside the page). */
  onClose?: () => void
  className?: string
}) {
  const { t } = useTranslation()
  const titleId = useId()
  const [hideSystem, setHideSystem] = useState(false)
  const [thread, setThread] = useState<string | null>(initialThread ?? null)
  return (
    <aside
      aria-labelledby={titleId}
      className={cn('flex min-h-96 flex-col rounded-lg border p-3', className)}
    >
      <header className="mb-2 flex flex-wrap items-center justify-between gap-2 border-b pb-2">
        <h2 id={titleId} className="text-sm font-semibold">
          {title}
        </h2>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <input
              type="checkbox"
              className="accent-primary"
              checked={hideSystem}
              onChange={(event) => setHideSystem(event.target.checked)}
            />
            {t('messaging.discussion.hideSystem')}
          </label>
          {onClose && (
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t('messaging.discussion.close')}
              onClick={onClose}
            >
              <X aria-hidden />
            </Button>
          )}
        </div>
      </header>
      {conversation.isPending ? (
        <LoadingState rows={3} />
      ) : conversation.isError ? (
        <ErrorState error={conversation.error} onRetry={() => void conversation.refetch()} />
      ) : (
        <ConversationPane
          conversation={conversation.data}
          spaceRole={spaceRole}
          includeSystem={!hideSystem}
          thread={thread}
          onThread={setThread}
          highlight={highlight}
          layout="narrow"
          emptyText={emptyText}
          composerLabel={composerLabel}
        />
      )}
    </aside>
  )
}
