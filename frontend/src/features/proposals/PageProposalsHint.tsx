import { Link } from '@tanstack/react-router'
import { GitPullRequestArrow } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useWiki } from '@/features/wiki/WikiContext'
import { openForPage } from './display'
import { useProposals } from './queries'

/** On a page with open proposals, a hint for its editors (who see proposals). */
export function PageProposalsHint({ pageId }: { pageId: string }) {
  const { t } = useTranslation()
  const { space, abilities } = useWiki()
  const open = useProposals(space.id, 'open', abilities.edit)
  const count = openForPage(open.items, pageId)
  if (!abilities.edit || count === 0) return null
  return (
    <Link
      to="/spaces/$spaceId/proposals"
      params={{ spaceId: space.id }}
      className="inline-flex items-center gap-1.5 rounded-md border border-dashed px-2 py-1 text-xs text-foreground hover:bg-muted"
    >
      <GitPullRequestArrow className="size-3.5" aria-hidden />
      {t('proposals.pageHint', { count })}
    </Link>
  )
}
