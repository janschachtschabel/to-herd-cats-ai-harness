import { useTranslation } from 'react-i18next'
import type { Space, WikiPage } from '@/lib/api'
import { usePageThread } from '../queries'
import { DiscussionPanel } from './DiscussionPanel'

/** A page's discussion beside it (spec 6.2). */
export function PageDiscussion({
  page,
  space,
  thread,
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
  return (
    <DiscussionPanel
      conversation={usePageThread(page.id)}
      spaceRole={space.my_role}
      title={t('messaging.discussion.title')}
      emptyText={t('messaging.discussion.empty')}
      composerLabel={t('messaging.discussion.composer')}
      thread={thread}
      highlight={highlight}
      onClose={onClose}
      className="h-[calc(100dvh-10rem)] lg:sticky lg:top-4"
    />
  )
}
