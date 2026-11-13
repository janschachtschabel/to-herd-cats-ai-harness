import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/features/shared/states'
import { useSpaceTags } from '@/features/wiki/tags/queries'
import { TagDialog } from './TagDialog'
import { TagTable } from './TagTable'

/** The space's own tags (`page.moderate` there); the system-wide ones are managed in
 *  the administration and only mentioned here. */
export function SpaceTags({ spaceId }: { spaceId: string }) {
  const { t } = useTranslation()
  const tags = useSpaceTags(spaceId)
  const [creating, setCreating] = useState(false)
  const own = (tags.data ?? []).filter((tag) => tag.space_id === spaceId)

  return (
    <section aria-labelledby="space-tags-heading" className="mt-8">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 id="space-tags-heading" className="text-base font-semibold">
            {t('tags.space.title')}
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">{t('tags.space.description')}</p>
        </div>
        <Button variant="outline" onClick={() => setCreating(true)}>
          <Plus aria-hidden />
          {t('tags.create.open')}
        </Button>
      </div>
      {tags.isPending ? (
        <LoadingState rows={2} />
      ) : tags.isError ? (
        <ErrorState error={tags.error} onRetry={() => void tags.refetch()} />
      ) : own.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('tags.space.empty')}</p>
      ) : (
        <TagTable scope={spaceId} tags={own} />
      )}
      <TagDialog open={creating} scope={spaceId} onOpenChange={setCreating} />
    </section>
  )
}
