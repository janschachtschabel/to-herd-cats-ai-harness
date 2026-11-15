import { FilePlus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/features/shared/states'
import { PageTree } from './PageTree'
import { useFilteredTree, useTree, type TreeFilter } from './queries'
import { TreeReviewFilter } from './review/TreeReviewFilter'
import { TreeTagFilter } from './tags/TreeTagFilter'
import { useSpaceTags } from './tags/queries'
import { useWiki } from './WikiContext'

/** The left column of a space: its page tree, or the pages the filters keep (a tag,
 *  a due review, or both). */
export function WikiTreePanel() {
  const { t } = useTranslation()
  const { space, abilities, createPage, tagFilter, reviewFilter } = useWiki()
  return (
    <aside aria-labelledby="wiki-tree-heading" className="min-w-0">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 id="wiki-tree-heading" className="text-sm font-semibold">
          {t('wiki.tree.title')}
        </h2>
        {abilities.create && (
          <Button size="sm" variant="ghost" onClick={() => createPage()}>
            <FilePlus aria-hidden />
            {t('wiki.create.open')}
          </Button>
        )}
      </div>
      <TreeTagFilter />
      <TreeReviewFilter />
      {tagFilter === null && !reviewFilter ? (
        <FullTree spaceId={space.id} />
      ) : (
        <FilteredTree spaceId={space.id} filter={{ tag: tagFilter, reviewDue: reviewFilter }} />
      )}
    </aside>
  )
}

function FullTree({ spaceId }: { spaceId: string }) {
  const { t } = useTranslation()
  const tree = useTree(spaceId)
  if (tree.isPending) return <LoadingState rows={3} />
  if (tree.isError) return <ErrorState error={tree.error} onRetry={() => void tree.refetch()} />
  if (tree.data.length === 0)
    return <p className="text-sm text-muted-foreground">{t('wiki.tree.empty')}</p>
  return <PageTree spaceId={spaceId} nodes={tree.data} />
}

/** The kept pages from the server's filters (`?tag=`, `?review_due=`); a page whose
 *  parent is kept too sits below it, the others at the top. */
function FilteredTree({ spaceId, filter }: { spaceId: string; filter: TreeFilter }) {
  const { t } = useTranslation()
  const tree = useFilteredTree(spaceId, filter)
  const tags = useSpaceTags(spaceId)
  const name = tags.data?.find((tag) => tag.id === filter.tag)?.name
  if (tree.isPending) return <LoadingState rows={3} />
  if (tree.isError) return <ErrorState error={tree.error} onRetry={() => void tree.refetch()} />
  if (tree.data.length === 0) {
    const empty = filter.reviewDue
      ? filter.tag
        ? 'wiki.review.emptyTagged'
        : 'wiki.review.empty'
      : 'wiki.tagFilter.empty'
    return <p className="text-sm text-muted-foreground">{t(empty)}</p>
  }
  const label = !filter.tag
    ? t('wiki.review.treeLabel')
    : filter.reviewDue
      ? t('wiki.review.treeLabelTagged', { name: name ?? '' })
      : name
        ? t('wiki.tagFilter.treeLabel', { name })
        : t('wiki.tagFilter.treeLabelAny')
  return <PageTree spaceId={spaceId} nodes={tree.data} label={label} />
}
