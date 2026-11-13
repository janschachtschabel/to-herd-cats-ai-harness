import { X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/features/shared/states'
import type { Space, WikiPage } from '@/lib/api'
import { ConversationPane } from '../conversation/ConversationPane'
import { usePageThread } from '../queries'

/**
 * A page's discussion beside it (spec 6.2): comments and the grey timeline of what
 * happened to the page, which can be hidden. Whoever sees the page sees it; writing
 * needs the same right as in the space's channels (the thread's `can_post`).
 */
export function PageDiscussion({
  page,
  space,
  thread: initialThread,
  highlight,
  onClose,
}: {
  page: WikiPage
  space: Space
  thread?: string
  highlight?: string
  onClose: () => void
}) {
  const { t } = useTranslation()
  const conversation = usePageThread(page.id)
  const [hideSystem, setHideSystem] = useState(false)
  const [thread, setThread] = useState<string | null>(initialThread ?? null)
  return (
    <aside
      aria-labelledby="discussion-title"
      className="flex h-[calc(100dvh-10rem)] min-h-96 flex-col rounded-lg border p-3 lg:sticky lg:top-4"
    >
      <header className="mb-2 flex flex-wrap items-center justify-between gap-2 border-b pb-2">
        <h2 id="discussion-title" className="text-sm font-semibold">
          {t('messaging.discussion.title')}
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
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t('messaging.discussion.close')}
            onClick={onClose}
          >
            <X aria-hidden />
          </Button>
        </div>
      </header>
      {conversation.isPending ? (
        <LoadingState rows={3} />
      ) : conversation.isError ? (
        <ErrorState error={conversation.error} onRetry={() => void conversation.refetch()} />
      ) : (
        <ConversationPane
          conversation={conversation.data}
          spaceRole={space.my_role}
          includeSystem={!hideSystem}
          thread={thread}
          onThread={setThread}
          highlight={highlight}
          layout="narrow"
          emptyText={t('messaging.discussion.empty')}
          composerLabel={t('messaging.discussion.composer')}
        />
      )}
    </aside>
  )
}
