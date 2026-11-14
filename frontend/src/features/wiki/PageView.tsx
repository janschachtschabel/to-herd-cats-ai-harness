import { useSearch } from '@tanstack/react-router'
import { MessageSquare } from 'lucide-react'
import { lazy, Suspense, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState } from '@/features/shared/states'
import { formatDateTime } from '@/lib/format'
import type { WikiPage } from '@/lib/api'
import { PageTickets } from '@/features/tickets/links/PageTickets'
import { AiLockBadge } from '@/features/ai/policy/AiLockBadge'
import { Attachments } from './attachments/Attachments'
import { MarkdownContent } from './MarkdownContent'
import { extractHeadings } from './markdown'
import { PageActions } from './PageActions'
import { Breadcrumbs, TableOfContents } from './PageNav'
import { PageTags } from './tags/PageTags'
import { useWiki } from './WikiContext'

// The discussion brings the conversation view; it loads when opened.
const PageDiscussion = lazy(() =>
  import('@/features/messaging/discussion/PageDiscussion').then((m) => ({
    default: m.PageDiscussion,
  })),
)

/** A page as everyone reads it (viewers get exactly this: no live connection), with
 *  its discussion beside it when opened (`?discussion=true` opens it at once). */
export function PageView({ page }: { page: WikiPage }) {
  const { t, i18n } = useTranslation()
  const { space, titles, abilities, createPage } = useWiki()
  const headings = useMemo(() => extractHeadings(page.content_md), [page.content_md])
  const search = useSearch({ strict: false })
  const [discussing, setDiscussing] = useState(search.discussion === true)
  return (
    <article aria-labelledby="page-title">
      <Breadcrumbs page={page} />
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="page-title" className="text-2xl font-semibold tracking-tight break-words">
            {page.title}
          </h2>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {page.status === 'draft' && <Badge variant="secondary">{t('wiki.page.draft')}</Badge>}
            {page.no_ai && <AiLockBadge moderates={abilities.moderate} />}
            <PageTags page={page} />
            <span>
              {t('wiki.page.updated', { when: formatDateTime(page.updated_at, i18n.language) })}
            </span>
          </div>
        </div>
        <div className="flex items-start gap-2">
          {!discussing && (
            <Button variant="outline" onClick={() => setDiscussing(true)}>
              <MessageSquare aria-hidden />
              {t('messaging.discussion.open')}
            </Button>
          )}
          <PageActions page={page} />
        </div>
      </div>
      <div
        className={
          discussing
            ? 'grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]'
            : 'grid gap-8 lg:grid-cols-[minmax(0,1fr)_12rem]'
        }
      >
        <div className="min-w-0">
          {page.content_md.trim() === '' ? (
            <p className="text-sm text-muted-foreground">{t('wiki.page.empty')}</p>
          ) : (
            <MarkdownContent
              spaceId={space.id}
              markdown={page.content_md}
              lookup={titles}
              onCreateMissing={abilities.create ? (title) => createPage({ title }) : undefined}
            />
          )}
        </div>
        {discussing ? (
          <Suspense fallback={<LoadingState rows={3} />}>
            <PageDiscussion
              page={page}
              space={space}
              thread={search.thread}
              highlight={search.message}
              onClose={() => setDiscussing(false)}
            />
          </Suspense>
        ) : (
          <aside className="hidden lg:block">
            <div className="sticky top-4">
              <TableOfContents headings={headings} />
            </div>
          </aside>
        )}
      </div>
      <PageTickets page={page} editable={abilities.edit} />
      <Attachments page={page} />
    </article>
  )
}
