import { Link } from '@tanstack/react-router'
import { ChevronRight } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { WikiPage } from '@/lib/api'
import type { Heading } from './markdown'
import { ancestorsOf } from './tree'
import { useWiki } from './WikiContext'

/** The pages above this one, each a link. */
export function Breadcrumbs({ page }: { page: WikiPage }) {
  const { t } = useTranslation()
  const { space, nodes } = useWiki()
  const chain = ancestorsOf(nodes, page.id)
  return (
    <nav aria-label={t('wiki.page.breadcrumbs')} className="mb-2 text-sm text-muted-foreground">
      <ol className="flex flex-wrap items-center gap-1">
        {chain.map((node) => (
          <li key={node.id} className="flex items-center gap-1">
            <Link
              to="/spaces/$spaceId/p/$"
              params={{ spaceId: space.id, _splat: node.path }}
              className="hover:text-foreground hover:underline"
            >
              {node.title}
            </Link>
            <ChevronRight aria-hidden className="size-3.5" />
          </li>
        ))}
        <li aria-current="page" className="text-foreground">
          {page.title}
        </li>
      </ol>
    </nav>
  )
}

/** h1–h3 of the page as in-page links; nothing for fewer than two headings. */
export function TableOfContents({ headings }: { headings: Heading[] }) {
  const { t } = useTranslation()
  if (headings.length < 2) return null
  return (
    <nav aria-labelledby="toc-heading" className="text-sm">
      <h3 id="toc-heading" className="mb-2 font-semibold">
        {t('wiki.page.toc')}
      </h3>
      <ul className="flex flex-col gap-1">
        {headings.map((heading, i) => (
          <li
            key={`${heading.id}-${i}`}
            style={{ paddingInlineStart: `${(heading.level - 1) * 12}px` }}
          >
            <a
              href={`#${heading.id}`}
              className="text-muted-foreground hover:text-foreground hover:underline"
            >
              {heading.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}
