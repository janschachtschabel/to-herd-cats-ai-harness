import { useTranslation } from 'react-i18next'
import { AgentBadge } from '@/features/agents/AgentBadge'
import type { ActivityEntry } from '@/lib/api'
import { usePageTitle } from './queries'
import { automationText } from './wording'

/** A paused automation: the sentence and the AI mark of its agent. */
export function AutomationSentence({ entry }: { entry: ActivityEntry }) {
  const { t } = useTranslation()
  return (
    <>
      {automationText(t, entry)}
      {entry.author?.type === 'agent' && (
        <>
          {' '}
          <AgentBadge />
        </>
      )}
    </>
  )
}

/** A page whose review came due: nobody caused it, so no author; the page by title
 *  (once read), else "a page". */
export function ReviewDueSentence({ entry }: { entry: ActivityEntry }) {
  const { t } = useTranslation()
  const title = usePageTitle(entry.conversation?.page_id ?? null)
  return <>{title ? t('activity.reviewDue.named', { title }) : t('activity.reviewDue.page')}</>
}
