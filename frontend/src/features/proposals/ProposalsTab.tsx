import { Link } from '@tanstack/react-router'
import { GitPullRequestArrow } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import type { Space } from '@/lib/api'
import { countLabel } from './display'
import { useProposals } from './queries'

/** The space's "Proposals" tab with the number of open ones (for page editors). */
export function ProposalsTab({
  space,
  linkProps,
}: {
  space: Space
  linkProps: { className: string; 'aria-current'?: 'page'; activeOptions: { exact: boolean } }
}) {
  const { t } = useTranslation()
  const open = useProposals(space.id, 'open')
  const count = open.items.length
  return (
    <Link to="/spaces/$spaceId/proposals" params={{ spaceId: space.id }} {...linkProps}>
      <GitPullRequestArrow className="size-4" aria-hidden />
      {t('proposals.tab')}
      {count > 0 && (
        <Badge variant="secondary" aria-label={t('proposals.tabCount', { count })}>
          {countLabel(count, open.hasMore)}
        </Badge>
      )}
    </Link>
  )
}
