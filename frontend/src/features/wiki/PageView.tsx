import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { formatDateTime } from '@/lib/format'
import type { WikiPage } from '@/lib/api'
import { Attachments } from './attachments/Attachments'
import { MarkdownContent } from './MarkdownContent'
import { extractHeadings } from './markdown'
import { PageActions } from './PageActions'
import { Breadcrumbs, TableOfContents } from './PageNav'
import { PageTags } from './tags/PageTags'
import { useWiki } from './WikiContext'

/** A page as everyone reads it (viewers get exactly this: no live connection). */
export function PageView({ page }: { page: WikiPage }) {
  const { t, i18n } = useTranslation()
  const { space, titles, abilities, createPage } = useWiki()
  const headings = useMemo(() => extractHeadings(page.content_md), [page.content_md])
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
            <PageTags page={page} />
            <span>
              {t('wiki.page.updated', { when: formatDateTime(page.updated_at, i18n.language) })}
            </span>
          </div>
        </div>
        <PageActions page={page} />
      </div>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_12rem]">
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
        <aside className="hidden lg:block">
          <div className="sticky top-4">
            <TableOfContents headings={headings} />
          </div>
        </aside>
      </div>
      <Attachments page={page} />
    </article>
  )
}
