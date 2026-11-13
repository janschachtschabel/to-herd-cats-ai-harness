import { FilePlus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/features/shared/states'
import { PageTree } from './PageTree'
import { useTaggedTree, useTree } from './queries'
import { TreeTagFilter } from './tags/TreeTagFilter'
import { useSpaceTags } from './tags/queries'
import { useWiki } from './WikiContext'

/** The left column of a space: its page tree, or the pages carrying the chosen tag. */
export function WikiTreePanel() {
  const { t } = useTranslation()
  const { space, abilities, createPage, tagFilter } = useWiki()
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
      {tagFilter === null ? (
        <FullTree spaceId={space.id} />
      ) : (
        <TaggedTree spaceId={space.id} tagId={tagFilter} />
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

/** The tagged pages from the server's `?tag=` filter; a page whose parent is tagged
 *  too sits below it, the others at the top. */
function TaggedTree({ spaceId, tagId }: { spaceId: string; tagId: string }) {
  const { t } = useTranslation()
  const tree = useTaggedTree(spaceId, tagId)
  const tags = useSpaceTags(spaceId)
  const name = tags.data?.find((tag) => tag.id === tagId)?.name
  if (tree.isPending) return <LoadingState rows={3} />
  if (tree.isError) return <ErrorState error={tree.error} onRetry={() => void tree.refetch()} />
  if (tree.data.length === 0)
    return <p className="text-sm text-muted-foreground">{t('wiki.tagFilter.empty')}</p>
  return (
    <PageTree
      spaceId={spaceId}
      nodes={tree.data}
      label={name ? t('wiki.tagFilter.treeLabel', { name }) : t('wiki.tagFilter.treeLabelAny')}
    />
  )
}
