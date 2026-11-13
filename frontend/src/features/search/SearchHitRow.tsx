import { FileText, Hash, MessageSquare, UsersRound } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { formatDateTime } from '@/lib/format'
import { Highlight } from './Highlight'
import type { AnyHit } from './queries'

/** One hit of the palette: a page (title, space) or a message (where, who, when). */
export function SearchHitRow({ hit }: { hit: AnyHit }) {
  const { t, i18n } = useTranslation()
  if (hit.type === 'page') {
    return (
      <>
        <div className="flex items-baseline justify-between gap-2">
          <span className="flex min-w-0 items-center gap-1.5 font-medium">
            <FileText className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
            <span className="truncate">{hit.title}</span>
          </span>
          <span className="shrink-0 text-xs text-muted-foreground">{hit.space_name}</span>
        </div>
        {hit.snippet && (
          <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
            <Highlight snippet={hit.snippet} />
          </p>
        )}
      </>
    )
  }
  const kind = hit.conversation.kind
  const Icon = kind === 'channel' ? Hash : kind === 'dm' ? UsersRound : MessageSquare
  const where =
    kind === 'channel'
      ? hit.conversation.name
      : kind === 'dm'
        ? t('messaging.dm.short')
        : t('messaging.discussion.title')
  return (
    <>
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1.5 font-medium">
          <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
          <span className="truncate">{where}</span>
          <span className="truncate font-normal text-muted-foreground">
            {t('search.messageBy', {
              author: hit.author?.name ?? t('messaging.message.unknownAuthor'),
            })}
          </span>
        </span>
        <time dateTime={hit.created_at} className="shrink-0 text-xs text-muted-foreground">
          {formatDateTime(hit.created_at, i18n.language)}
        </time>
      </div>
      <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
        <Highlight snippet={hit.snippet} />
      </p>
    </>
  )
}
