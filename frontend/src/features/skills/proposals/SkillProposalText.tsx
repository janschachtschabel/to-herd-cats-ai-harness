import { useTranslation } from 'react-i18next'
import { DiffLines } from '@/features/wiki/versions/DiffLines'
import { MarkdownContent } from '@/features/wiki/MarkdownContent'
import { lineDiff } from './diff'
import type { SkillProposalDetail } from './queries'

/** What a proposal holds: for a change, the skill as it is now against the proposed
 *  description and text (insertions and deletions marked, not by colour alone); for
 *  a new skill, its description and text as the agent would load it. */
export function SkillProposalText({ proposal }: { proposal: SkillProposalDetail }) {
  const { t } = useTranslation()
  const { proposed, current } = proposal
  if (!current) {
    return (
      <section aria-label={t('skills.proposals.proposedText')} className="flex flex-col gap-2">
        <p className="text-sm">
          <span className="font-medium">{t('skills.fields.description')}: </span>
          {proposed.description}
        </p>
        <div className="rounded-lg border p-4">
          <MarkdownContent spaceId={proposal.space_id ?? ''} markdown={proposed.content} />
        </div>
      </section>
    )
  }
  const description = lineDiff(current.description, proposed.description)
  const content = lineDiff(current.content, proposed.content)
  const same = (hunks: typeof content) => hunks.every((h) => h.kind === 'equal')
  return (
    <section aria-label={t('proposals.diffLabel')} className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">
        {t('skills.proposals.against', { number: current.number })}
      </p>
      {!same(description) && (
        <div className="flex flex-col gap-1">
          <h2 className="text-sm font-medium">{t('skills.fields.description')}</h2>
          <DiffLines hunks={description} />
        </div>
      )}
      <div className="flex flex-col gap-1">
        <h2 className="text-sm font-medium">{t('skills.fields.content')}</h2>
        {same(content) ? (
          <p className="text-sm text-muted-foreground">{t('skills.proposals.sameText')}</p>
        ) : (
          <DiffLines hunks={content} />
        )}
      </div>
    </section>
  )
}
