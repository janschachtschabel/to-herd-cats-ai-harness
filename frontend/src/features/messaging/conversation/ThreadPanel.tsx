import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadMore, LoadingState } from '@/features/shared/states'
import type { Message } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Composer } from './Composer'
import { ConversationContext, useConversationView } from './ConversationContext'
import { MessageItem } from './MessageItem'
import { PendingItem } from './PendingItem'
import { usePending } from './pending'
import { useReplies } from './queries'
import { CannotPost } from './CannotPost'

/** A message's thread beside the conversation: the message, its replies (oldest
 *  first), and a composer for one more. */
export function ThreadPanel({
  parentId,
  parent,
  onClose,
  inline = false,
}: {
  parentId: string
  /** In place of the conversation (a narrow panel) rather than beside it. */
  inline?: boolean
  /** The message itself, if it is among the loaded ones. */
  parent: Message | undefined
  onClose: () => void
}) {
  const { t } = useTranslation()
  const view = useConversationView()
  const { conversation } = view
  const replies = useReplies(conversation.id, parentId)
  const pending = usePending(conversation.id, parentId)
  const sent = new Set(replies.items.map((m) => m.client_id))
  const inThread = { ...view, openThread: undefined }

  return (
    <aside
      aria-label={t('messaging.thread.title')}
      className={cn('flex min-h-0 w-full flex-col', !inline && 'border-l pl-4 lg:w-96 lg:shrink-0')}
    >
      <header className="flex items-center justify-between gap-2 pb-2">
        <h2 className="text-sm font-semibold">{t('messaging.thread.title')}</h2>
        <Button variant="ghost" size="icon-sm" aria-label={t('actions.close')} onClick={onClose}>
          <X aria-hidden />
        </Button>
      </header>
      <ConversationContext.Provider value={inThread}>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {parent && (
            <div className="border-b pb-2">
              <MessageItem message={parent} />
            </div>
          )}
          {replies.isPending ? (
            <LoadingState rows={2} />
          ) : replies.isError ? (
            <ErrorState error={replies.error} onRetry={() => void replies.refetch()} />
          ) : (
            <>
              <p className="py-2 text-xs text-muted-foreground">
                {t('messaging.thread.replies', { count: replies.items.length })}
              </p>
              <ol className="flex flex-col gap-0.5">
                {replies.items.map((message) => (
                  <li key={message.id}>
                    <MessageItem message={message} />
                  </li>
                ))}
                {pending
                  .filter((p) => !sent.has(p.clientId))
                  .map((p) => (
                    <li key={p.clientId}>
                      <PendingItem pending={p} />
                    </li>
                  ))}
              </ol>
              <LoadMore
                hasMore={replies.hasMore}
                loading={replies.loadingMore}
                onLoad={replies.loadMore}
              />
            </>
          )}
        </div>
        {view.abilities.post ? (
          <Composer
            key={parentId}
            conversationId={conversation.id}
            parentId={parentId}
            label={t('messaging.thread.composer')}
          />
        ) : (
          <CannotPost conversation={conversation} />
        )}
      </ConversationContext.Provider>
    </aside>
  )
}
