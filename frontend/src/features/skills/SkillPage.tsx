import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Archive, ArchiveRestore, Download, Pencil } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/queries'
import { SaveError } from '@/features/shared/forms'
import { ErrorState, LoadingState, PageHeader } from '@/features/shared/states'
import { spaceQuery } from '@/features/spaces/queries'
import { MarkdownContent } from '@/features/wiki/MarkdownContent'
import { skillAbilities } from './abilities'
import { skillExportUrl, useArchiveSkill, useSkill } from './queries'
import { SkillAuthor } from './SkillAuthor'
import { SkillFormDialog } from './SkillFormDialog'
import { SkillVersions } from './SkillVersions'

/** One skill: its description and text as the agent loads it, where it belongs, its
 *  versions; editing, archiving and restoring for those who manage it, the export
 *  (a SKILL.md) for everyone who reads it. */
export function SkillPage({ skillId }: { skillId: string }) {
  const { t } = useTranslation()
  const me = useMe()
  const skill = useSkill(skillId)
  const spaceId = skill.data?.space_id ?? null
  const space = useQuery({ ...spaceQuery(spaceId ?? ''), enabled: spaceId !== null })
  const archive = useArchiveSkill(skillId)
  const [editing, setEditing] = useState(false)

  if (skill.isPending) return <LoadingState />
  if (skill.isError) return <ErrorState error={skill.error} onRetry={() => void skill.refetch()} />
  const data = skill.data
  const abilities = skillAbilities(me, spaceId ? (space.data ?? null) : null)
  const manage = abilities.manage && (spaceId === null || space.data !== undefined)
  const archived = data.state === 'archived'

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={data.name}
        description={data.description}
        actions={
          <div className="flex flex-wrap gap-2">
            {manage && (
              <>
                <Button variant="outline" onClick={() => setEditing(true)}>
                  <Pencil aria-hidden />
                  {t('actions.edit')}
                </Button>
                <Button
                  variant="outline"
                  disabled={archive.isPending}
                  onClick={() => archive.mutate({ archive: !archived, version: data.version })}
                >
                  {archived ? <ArchiveRestore aria-hidden /> : <Archive aria-hidden />}
                  {archived ? t('skills.unarchive') : t('skills.archive')}
                </Button>
              </>
            )}
            <Button variant="outline" asChild>
              <a href={skillExportUrl(data.id)} download>
                <Download aria-hidden />
                {t('skills.export')}
              </a>
            </Button>
          </div>
        }
      >
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {spaceId ? (
            <Badge variant="outline" asChild>
              <Link to="/spaces/$spaceId/skills" params={{ spaceId }}>
                {space.data?.name ?? t('skills.scope.space')}
              </Link>
            </Badge>
          ) : (
            <Badge variant="outline">{t('skills.scope.org')}</Badge>
          )}
          <Badge variant={archived ? 'secondary' : 'outline'}>
            {t(`skills.state.${data.state}`)}
          </Badge>
          <SkillAuthor author={data.author} />
        </div>
      </PageHeader>
      <SaveError error={archive.error} onReload={() => void skill.refetch()} />
      <section aria-labelledby="skill-text" className="rounded-lg border p-4">
        <h2 id="skill-text" className="sr-only">
          {t('skills.text')}
        </h2>
        <MarkdownContent spaceId={spaceId ?? ''} markdown={data.content} />
      </section>
      <SkillVersions skill={data} manage={manage} />
      {manage && <SkillFormDialog open={editing} skill={data} onOpenChange={setEditing} />}
    </div>
  )
}
