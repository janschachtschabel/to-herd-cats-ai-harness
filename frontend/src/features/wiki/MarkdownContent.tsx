// Ported-from: to-herd-cats-ai@46352bb:frontend/src/features/wiki/MarkdownContent.tsx
import { Link } from '@tanstack/react-router'
import type { ComponentPropsWithoutRef, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { headingId, resolveWikiLinks, safeUrl } from './markdown'

const WIKI = 'wiki:'
const MISSING = 'wiki-missing:'

function urlTransform(url: string): string {
  return url.startsWith(WIKI) || url.startsWith(MISSING) ? url : safeUrl(url)
}

function plainText(children: ReactNode): string {
  if (typeof children === 'string') return children
  if (Array.isArray(children)) return children.map(plainText).join('')
  if (children && typeof children === 'object' && 'props' in children) {
    return plainText((children as { props: { children?: ReactNode } }).props.children)
  }
  return ''
}

function heading(level: 1 | 2 | 3) {
  const Tag = `h${level}` as const
  return function Heading({
    children,
    node: _node,
    ...rest
  }: ComponentPropsWithoutRef<typeof Tag> & { node?: unknown }) {
    return (
      <Tag id={headingId(plainText(children))} {...rest}>
        {children}
      </Tag>
    )
  }
}

function MissingLink({
  title,
  children,
  onCreate,
}: {
  title: string
  children: ReactNode
  onCreate?: (title: string) => void
}) {
  const { t } = useTranslation()
  return (
    <span className="wiki-missing" title={t('wiki.links.missing')}>
      {children}
      {onCreate && (
        <button
          type="button"
          className="ml-1 rounded-sm text-xs underline underline-offset-2"
          aria-label={t('wiki.links.createNamed', { title })}
          onClick={() => onCreate(title)}
        >
          {t('wiki.links.create')}
        </button>
      )}
    </span>
  )
}

interface Props {
  /** The space `[[wiki links]]` are resolved in. */
  spaceId: string
  markdown: string
  /** Lower-case page title → page path. */
  lookup?: Map<string, string>
  /** Offered on a link to a page that does not exist (only to people who may create). */
  onCreateMissing?: (title: string) => void
}

/** Page Markdown as HTML: GFM, never raw HTML (no rehype-raw), links only to http,
 *  https, mailto and relative targets, wiki links as router links. */
export function MarkdownContent({ spaceId, markdown, lookup, onCreateMissing }: Props) {
  const source = lookup ? resolveWikiLinks(markdown, lookup) : markdown
  const components: Components = {
    h1: heading(1),
    h2: heading(2),
    h3: heading(3),
    a: ({ href, children }) => {
      if (!href) return <span>{children}</span>
      if (href.startsWith(WIKI)) {
        const path = decodeURIComponent(href.slice(WIKI.length))
        return (
          <Link to="/spaces/$spaceId/p/$" params={{ spaceId, _splat: path }}>
            {children}
          </Link>
        )
      }
      if (href.startsWith(MISSING)) {
        const title = decodeURIComponent(href.slice(MISSING.length))
        return (
          <MissingLink title={title} onCreate={onCreateMissing}>
            {children}
          </MissingLink>
        )
      }
      const external = /^(https?:|mailto:)/i.test(href)
      return (
        <a href={href} {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>
          {children}
        </a>
      )
    },
    img: ({ src, alt }) =>
      typeof src === 'string' && src ? <img src={src} alt={alt ?? ''} /> : null,
  }
  return (
    <div className="wiki-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={urlTransform}
        components={components}
      >
        {source}
      </ReactMarkdown>
    </div>
  )
}
