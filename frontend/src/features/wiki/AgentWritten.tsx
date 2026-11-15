import { Bot } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { AgentBadge } from '@/features/agents/AgentBadge'
import { VisibleRunLink } from '@/features/runs/RunBits'
import type { WikiPage } from '@/lib/api'
import { isMemoryPage } from './tree'
import { useVersions } from './versions/queries'

/** The AI mark on a page an agent changed last, with a link to the run that wrote the
 *  newest version (for those who may read the run). */
export function AgentWritten({ page }: { page: WikiPage }) {
  if (page.updated_by.type !== 'agent') return null
  return (
    <>
      <AgentBadge />
      <LatestRun pageId={page.id} />
    </>
  )
}

function LatestRun({ pageId }: { pageId: string }) {
  const versions = useVersions(pageId)
  const latest = versions.items[0]
  if (!latest?.ai || !latest.run_id) return null
  return <VisibleRunLink runId={latest.run_id} />
}

/** On an agent's memory page: an agent keeps it, and people may correct it. */
export function MemoryNote({ page }: { page: WikiPage }) {
  const { t } = useTranslation()
  if (!isMemoryPage(page)) return null
  return (
    <p className="mb-4 flex items-start gap-2 rounded-lg border border-violet-300 bg-violet-50 p-3 text-sm text-violet-900 dark:border-violet-500/40 dark:bg-violet-500/10 dark:text-violet-100">
      <Bot aria-hidden className="mt-0.5 size-4 shrink-0" />
      <span>{t('wiki.memory.note')}</span>
    </p>
  )
}
