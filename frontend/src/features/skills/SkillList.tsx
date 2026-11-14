import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { SkillAuthor } from './SkillAuthor'
import { useSkills, type SkillFilter } from './queries'

/** A page-wise list of skills by name: where each belongs, its state and author. */
export function SkillList({
  filter,
  spaceNames,
}: {
  filter: SkillFilter
  /** Names of spaces by id, to say where a space's skill belongs. */
  spaceNames?: ReadonlyMap<string, string>
}) {
  const { t } = useTranslation()
  const skills = useSkills(filter)
  if (skills.isPending) return <LoadingState />
  if (skills.isError) {
    return <ErrorState error={skills.error} onRetry={() => void skills.refetch()} />
  }
  if (skills.items.length === 0) {
    return <EmptyState text={filter.q ? t('skills.list.noMatch') : t('skills.list.empty')} />
  }
  return (
    <>
      <ul aria-label={t('skills.list.label')} className="divide-y rounded-lg border">
        {skills.items.map((skill) => (
          <li key={skill.id} className="flex flex-col gap-1 p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Link
                to="/skills/$skillId"
                params={{ skillId: skill.id }}
                className="font-medium underline-offset-4 hover:underline"
              >
                {skill.name}
              </Link>
              <Badge variant="outline">
                {skill.space_id
                  ? (spaceNames?.get(skill.space_id) ?? t('skills.scope.space'))
                  : t('skills.scope.org')}
              </Badge>
              {skill.state === 'archived' && (
                <Badge variant="secondary">{t('skills.state.archived')}</Badge>
              )}
            </div>
            <p className="text-muted-foreground">{skill.description}</p>
            <SkillAuthor author={skill.author} />
          </li>
        ))}
      </ul>
      <LoadMore hasMore={skills.hasMore} loading={skills.loadingMore} onLoad={skills.loadMore} />
    </>
  )
}
