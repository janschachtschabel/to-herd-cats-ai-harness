import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { useSystemTags } from '@/features/tags/queries'
import { TagDialog } from '@/features/tags/TagDialog'
import { TagTable } from '@/features/tags/TagTable'

/** The system-wide tags (`tag.manage`): usable in every space. */
export function TagsPage() {
  const { t } = useTranslation()
  const tags = useSystemTags()
  const [creating, setCreating] = useState(false)

  return (
    <div>
      <PageHeader
        title={t('tags.title')}
        description={t('tags.description')}
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden />
            {t('tags.create.open')}
          </Button>
        }
      />
      {tags.isPending ? (
        <LoadingState />
      ) : tags.isError ? (
        <ErrorState error={tags.error} onRetry={() => void tags.refetch()} />
      ) : tags.items.length === 0 ? (
        <EmptyState text={t('tags.empty')} />
      ) : (
        <TagTable scope={null} tags={tags.items} />
      )}
      <LoadMore hasMore={tags.hasMore} loading={tags.loadingMore} onLoad={tags.loadMore} />
      <TagDialog open={creating} scope={null} onOpenChange={setCreating} />
    </div>
  )
}
