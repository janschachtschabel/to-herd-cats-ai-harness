import { Link } from '@tanstack/react-router'
import { Eye, Hash, UsersRound } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { useMe } from '@/features/auth/queries'
import type { Conversation, Space } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { conversationLabel } from '../display'

/** Name and topic of a channel (with its space), or the people of a direct message,
 *  and every time an administrator looked into it (spec 5.5). */
export function ConversationHeader({
  conversation,
  space,
}: {
  conversation: Conversation
  space: Space | undefined
}) {
  const { t, i18n } = useTranslation()
  const me = useMe()
  const Icon = conversation.kind === 'dm' ? UsersRound : Hash
  return (
    <header className="mb-3 border-b pb-3">
      <div className="flex flex-wrap items-center gap-2">
        <Icon className="size-5 text-muted-foreground" aria-hidden />
        <h1 className="text-xl font-semibold tracking-tight break-words">
          {conversationLabel(t, conversation, me?.user.id).replace(/^# /, '')}
        </h1>
        {conversation.archived_at && (
          <Badge variant="secondary">{t('messaging.channel.archived')}</Badge>
        )}
        {space && (
          <Link
            to="/spaces/$spaceId"
            params={{ spaceId: space.id }}
            className="text-sm text-muted-foreground hover:text-foreground hover:underline"
          >
            {t('messaging.channel.inSpace', { space: space.name })}
          </Link>
        )}
      </div>
      {conversation.topic && (
        <p className="mt-1 text-sm text-muted-foreground">{conversation.topic}</p>
      )}
      {(conversation.inspections ?? []).length > 0 && (
        <ul className="mt-2 flex flex-col gap-1" aria-label={t('messaging.dm.inspectionsLabel')}>
          {(conversation.inspections ?? []).map((note) => (
            <li
              key={note.at}
              className="flex items-center gap-2 rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-900 dark:bg-amber-500/10 dark:text-amber-200"
            >
              <Eye className="size-3.5 shrink-0" aria-hidden />
              {t('messaging.dm.inspected', {
                when: formatDateTime(note.at, i18n.language),
                admin: note.admin_name,
              })}
            </li>
          ))}
        </ul>
      )}
    </header>
  )
}
