import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { safeUrl } from '@/features/wiki/markdown'

const MENTION = 'user:'
const TOKEN = /@\[([^\]\n]*)\]\((user:[0-9a-fA-F-]{36})\)/g

/** A mention keeps its `user:` target (rendered as a name, never as a link); every
 *  other target passes the wiki's check (http, https, mailto, relative). */
function urlTransform(url: string): string {
  return url.startsWith(MENTION) ? url : safeUrl(url)
}

/** A message's Markdown, with the wiki's safe renderer: GFM, never raw HTML (no
 *  rehype-raw), links only to allowed targets. `@[Name](user:<id>)` shows as a
 *  highlighted name, more so when it names `meId`. */
export function MessageMarkdown({ markdown, meId }: { markdown: string; meId?: string }) {
  const components: Components = {
    a: ({ href, children }) => {
      if (!href) return <span>{children}</span>
      if (href.startsWith(MENTION)) {
        const mine = href.slice(MENTION.length).toLowerCase() === meId?.toLowerCase()
        return <span className={mine ? 'mention mention-me' : 'mention'}>{children}</span>
      }
      const external = /^(https?:|mailto:)/i.test(href)
      return (
        <a href={href} {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>
          {children}
        </a>
      )
    },
    img: ({ src, alt }) =>
      typeof src === 'string' && src ? <img src={src} alt={alt ?? ''} loading="lazy" /> : null,
  }
  // The "@" goes into the mention's text, so the name reads as one chip.
  const source = markdown.replace(TOKEN, '[@$1]($2)')
  return (
    <div className="wiki-prose message-prose">
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
