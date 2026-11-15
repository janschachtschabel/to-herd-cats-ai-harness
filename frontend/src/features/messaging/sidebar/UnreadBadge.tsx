import { useTranslation } from 'react-i18next'
import type { Unread } from '@/lib/api'
import { badgeCount } from '@/lib/format'
import { cn } from '@/lib/utils'

/** The unread count beside a conversation (above 99: "99+"); mentions of me make it
 *  stand out. */
export function UnreadBadge({ unread }: { unread: Unread | undefined }) {
  const { t } = useTranslation()
  if (!unread || (unread.unread === 0 && unread.mentions === 0)) return null
  const mentioned = unread.mentions > 0
  const count = mentioned ? unread.mentions : unread.unread
  return (
    <span
      className={cn(
        'ml-auto inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full px-1.5 text-[11px] font-semibold tabular-nums',
        mentioned
          ? 'bg-destructive text-white'
          : 'bg-sidebar-primary text-sidebar-primary-foreground',
      )}
    >
      <span aria-hidden>
        {mentioned ? '@' : ''}
        {badgeCount(count)}
      </span>
      <span className="sr-only">
        {mentioned
          ? t('messaging.unread.mentions', { count: unread.mentions })
          : t('messaging.unread.messages', { count: unread.unread })}
      </span>
    </span>
  )
}
