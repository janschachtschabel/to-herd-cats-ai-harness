import { Eye, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { MarkdownContent } from '@/features/wiki/MarkdownContent'
import { formatDateTime } from '@/lib/format'
import { SkillAuthor } from './SkillAuthor'
import {
  useRestoreSkillVersion,
  useSkillVersion,
  useSkillVersions,
  type SkillDetail,
  type SkillVersion,
} from './queries'

/** A skill's versions, newest first: who and when, the text of one on request, and
 *  (for those who manage the skill) restoring one as a new version. */
export function SkillVersions({ skill, manage }: { skill: SkillDetail; manage: boolean }) {
  const { t, i18n } = useTranslation()
  const versions = useSkillVersions(skill.id)
  const restore = useRestoreSkillVersion(skill.id)
  const [viewing, setViewing] = useState<number | null>(null)
  const [restoring, setRestoring] = useState<SkillVersion | null>(null)
  const newest = versions.items[0]?.number

  return (
    <section aria-labelledby="skill-versions" className="flex flex-col gap-3">
      <h2 id="skill-versions" className="text-base font-semibold">
        {t('skills.versions.title')}
      </h2>
      {versions.isPending ? (
        <LoadingState rows={2} />
      ) : versions.isError ? (
        <ErrorState error={versions.error} onRetry={() => void versions.refetch()} />
      ) : (
        <ul aria-label={t('skills.versions.title')} className="divide-y rounded-lg border text-sm">
          {versions.items.map((v) => (
            <li key={v.number} className="flex flex-col gap-2 p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium">{t('skills.versions.number', { number: v.number })}</p>
                  <p className="text-muted-foreground">{v.description}</p>
                  <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <SkillAuthor author={v.author} />
                    {formatDateTime(v.created_at, i18n.language)}
                  </p>
                </div>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={t('skills.versions.viewNamed', { number: v.number })}
                    aria-expanded={viewing === v.number}
                    onClick={() => setViewing(viewing === v.number ? null : v.number)}
                  >
                    <Eye aria-hidden />
                  </Button>
                  {manage && v.number !== newest && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={t('skills.versions.restoreNamed', { number: v.number })}
                      onClick={() => setRestoring(v)}
                    >
                      <RotateCcw aria-hidden />
                    </Button>
                  )}
                </div>
              </div>
              {viewing === v.number && <VersionText skillId={skill.id} number={v.number} />}
            </li>
          ))}
        </ul>
      )}
      <LoadMore
        hasMore={versions.hasMore}
        loading={versions.loadingMore}
        onLoad={versions.loadMore}
      />
      {manage && (
        <ConfirmDialog
          open={restoring !== null}
          title={t('skills.versions.restoreTitle')}
          text={t('skills.versions.restoreText', { number: restoring?.number ?? 0 })}
          confirmLabel={t('skills.versions.restore')}
          pending={restore.isPending}
          error={restore.error}
          onOpenChange={(open) => !open && setRestoring(null)}
          onConfirm={() =>
            restoring &&
            restore.mutate(
              { number: restoring.number, version: skill.version },
              { onSuccess: () => setRestoring(null) },
            )
          }
        />
      )}
    </section>
  )
}

function VersionText({ skillId, number }: { skillId: string; number: number }) {
  const version = useSkillVersion(skillId, number)
  if (version.isPending) return <LoadingState rows={2} />
  if (version.isError) {
    return <ErrorState error={version.error} onRetry={() => void version.refetch()} />
  }
  return (
    <div className="rounded-md bg-muted/40 p-3">
      <MarkdownContent spaceId="" markdown={version.data.content} />
    </div>
  )
}
