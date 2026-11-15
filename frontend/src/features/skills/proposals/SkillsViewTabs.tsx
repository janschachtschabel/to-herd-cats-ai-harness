import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { countLabel } from '@/features/proposals/display'
import { cn } from '@/lib/utils'

export type SkillsView = 'skills' | 'proposals'

/** The two views of a skills area for those who decide proposals: the skills, and
 *  the proposals with the number of open ones. `link` renders each view's link (the
 *  same address with or without `?view=proposals`). */
export function SkillsViewTabs({
  view,
  open,
  more,
  link,
}: {
  view: SkillsView
  open: number
  more: boolean
  link: (view: SkillsView, props: { className: string; children: ReactNode }) => ReactNode
}) {
  const { t } = useTranslation()
  const tab = (name: SkillsView) =>
    cn(
      '-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium',
      view === name
        ? 'border-primary text-foreground'
        : 'border-transparent text-muted-foreground hover:text-foreground',
    )
  return (
    <nav aria-label={t('skills.proposals.views')} className="mb-4 flex border-b">
      {link('skills', { className: tab('skills'), children: t('skills.tab') })}
      {link('proposals', {
        className: tab('proposals'),
        children: (
          <>
            {t('skills.proposals.tab')}
            {open > 0 && (
              <Badge variant="secondary" aria-label={t('proposals.tabCount', { count: open })}>
                {countLabel(open, more)}
              </Badge>
            )}
          </>
        ),
      })}
    </nav>
  )
}
