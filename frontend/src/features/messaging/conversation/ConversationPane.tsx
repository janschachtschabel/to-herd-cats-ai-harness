import { useTranslation } from 'react-i18next'
import { agentOf } from '@/features/agents/display'
import { RunProgress } from '@/features/agents/RunProgress'
import { useMe } from '@/features/auth/queries'
import type { Conversation, SpaceRole } from '@/lib/api'
import { cn } from '@/lib/utils'
import { conversationAbilities } from '../abilities'
import { CannotPost } from './CannotPost'
import { Composer } from './Composer'
import { ConversationContext, type ConversationView } from './ConversationContext'
import { MessageList } from './MessageList'
import { usePending } from './pending'
import { useMessages } from './queries'
import { ThreadPanel } from './ThreadPanel'
import { useReadTracking } from './useReadTracking'

/**
 * An open conversation: its history and composer, and a thread beside it (`wide`) or
 * in its place (`narrow`, as in a page's discussion). What one may do comes from the
 * conversation's `can_post` and the space's `my_role` only.
 */
export function ConversationPane({
  conversation,
  spaceRole,
  includeSystem = true,
  thread,
  onThread,
  highlight,
  layout = 'wide',
  emptyText,
  composerLabel,
}: {
  conversation: Conversation
  spaceRole: SpaceRole | null | undefined
  includeSystem?: boolean
  thread: string | null
  onThread: (messageId: string | null) => void
  highlight?: string
  layout?: 'wide' | 'narrow'
  emptyText: string
  composerLabel: string
}) {
  const { t } = useTranslation()
  const me = useMe()
  const meId = me?.user.id
  const list = useMessages(conversation.id, includeSystem)
  const pending = usePending(conversation.id, null)
  const newBefore = useReadTracking(conversation.id, list, meId)
  const abilities = conversationAbilities(conversation, spaceRole)
  const view: ConversationView = {
    conversation,
    abilities,
    meId,
    openThread: (id) => onThread(id),
    highlight,
  }
  const parent = thread ? list.messages.find((m) => m.id === thread) : undefined
  const narrowThread = layout === 'narrow' && thread !== null
  const agent = agentOf(conversation)

  return (
    <ConversationContext.Provider value={view}>
      <div className="flex min-h-0 flex-1 gap-4">
        {!narrowThread && (
          <section
            aria-label={t('messaging.list.section')}
            className={cn('flex min-h-0 min-w-0 flex-1 flex-col', thread && 'hidden lg:flex')}
          >
            <MessageList
              list={list}
              pending={pending}
              newBefore={newBefore}
              emptyText={emptyText}
            />
            <RunProgress
              conversationId={conversation.id}
              place={agent ? { kind: 'dm' } : { kind: 'conversation', onOpenThread: onThread }}
            />
            {abilities.post ? (
              <Composer
                key={conversation.id}
                conversationId={conversation.id}
                label={composerLabel}
              />
            ) : (
              <CannotPost conversation={conversation} />
            )}
          </section>
        )}
        {thread && (
          <ThreadPanel
            key={thread}
            parentId={thread}
            parent={parent}
            inline={narrowThread}
            onClose={() => onThread(null)}
          />
        )}
      </div>
    </ConversationContext.Provider>
  )
}
