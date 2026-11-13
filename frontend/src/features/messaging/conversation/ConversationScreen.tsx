import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { spaceQuery } from '@/features/spaces/queries'
import { EmptyState, ErrorState, LoadingState } from '@/features/shared/states'
import { ApiError, type Conversation } from '@/lib/api'
import { useConversation } from '../queries'
import { ConversationHeader } from './ConversationHeader'
import { ConversationPane } from './ConversationPane'

/** The conversation one may no longer (or never could) see: say so and offer a way on. */
function Gone() {
  const { t } = useTranslation()
  return (
    <EmptyState text={t('messaging.conversation.gone')}>
      <Button variant="outline" asChild>
        <Link to="/activity">{t('messaging.conversation.toActivity')}</Link>
      </Button>
    </EmptyState>
  )
}

/** A channel or direct message as its own screen (`/c/<id>`); `thread` opens a
 *  message's thread beside it, `message` marks one (from search or the activity). */
export function ConversationScreen({
  conversationId,
  thread,
  message,
}: {
  conversationId: string
  thread?: string
  message?: string
}) {
  const conversation = useConversation(conversationId)
  // Checked before the data: a conversation one lost access to answers 404 on the
  // next look, while the old data is still cached.
  if (conversation.error instanceof ApiError && conversation.error.status === 404) return <Gone />
  if (conversation.isPending) return <LoadingState />
  if (conversation.isError) {
    return <ErrorState error={conversation.error} onRetry={() => void conversation.refetch()} />
  }
  return <OpenConversation conversation={conversation.data} thread={thread} message={message} />
}

function OpenConversation({
  conversation,
  thread,
  message,
}: {
  conversation: Conversation
  thread?: string
  message?: string
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const spaceId = conversation.space_id
  const space = useQuery({ ...spaceQuery(spaceId ?? ''), enabled: spaceId !== null })
  const setThread = (id: string | null) =>
    void navigate({
      to: '/c/$conversationId',
      params: { conversationId: conversation.id },
      search: id ? { thread: id } : {},
    })
  return (
    <div className="flex h-[calc(100dvh-7rem)] min-h-80 flex-col">
      <ConversationHeader conversation={conversation} space={space.data} />
      <ConversationPane
        key={conversation.id}
        conversation={conversation}
        spaceRole={space.data?.my_role}
        thread={thread ?? null}
        onThread={setThread}
        highlight={message}
        emptyText={t('messaging.list.empty')}
        composerLabel={t('messaging.composer.label', {
          name: conversation.kind === 'channel' ? `#${conversation.name}` : t('messaging.dm.short'),
        })}
      />
    </div>
  )
}
