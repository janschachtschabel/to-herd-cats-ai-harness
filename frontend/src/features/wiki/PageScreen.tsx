import { lazy, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { EmptyState, ErrorState, LoadingState } from '@/features/shared/states'
import { ApiError } from '@/lib/api'
import { PageView } from './PageView'
import { usePageByPath } from './queries'
import { useWiki } from './WikiContext'

export type PageMode = 'edit' | 'live' | 'versions'

// The editors and the version history load only when opened (the live editor brings
// Tiptap and Yjs); reading a page needs none of them.
const MarkdownEditor = lazy(() =>
  import('./editor/MarkdownEditor').then((m) => ({ default: m.MarkdownEditor })),
)
const VersionsPanel = lazy(() =>
  import('./versions/VersionsPanel').then((m) => ({ default: m.VersionsPanel })),
)

/** The page at `path`, as reader, Markdown editor, live editor or version history.
 *  Editing modes fall back to reading without page.edit. */
export function PageScreen({ path, mode }: { path: string; mode?: PageMode }) {
  const { t } = useTranslation()
  const { space, abilities, createPage } = useWiki()
  const page = usePageByPath(space.id, path)
  if (page.isPending) return <LoadingState />
  if (page.isError) {
    if (page.error instanceof ApiError && page.error.status === 404) {
      return (
        <EmptyState text={t('wiki.page.notFound')}>
          {abilities.create && (
            <Button onClick={() => createPage()}>{t('wiki.create.open')}</Button>
          )}
        </EmptyState>
      )
    }
    return <ErrorState error={page.error} onRetry={() => void page.refetch()} />
  }
  const data = page.data
  return (
    <Suspense fallback={<LoadingState />}>
      {mode === 'versions' ? (
        <VersionsPanel page={data} />
      ) : mode === 'edit' && abilities.edit ? (
        <MarkdownEditor key={data.id} page={data} />
      ) : (
        <PageView page={data} />
      )}
    </Suspense>
  )
}
