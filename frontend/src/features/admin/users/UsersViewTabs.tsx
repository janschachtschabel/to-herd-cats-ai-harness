import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { badgeCount } from '@/lib/format'
import { cn } from '@/lib/utils'

export type UsersFilter = 'all' | 'pending'

/** Everyone, or only the self-registered accounts awaiting approval (with their
 *  number). */
export function UsersViewTabs({ filter, pending }: { filter: UsersFilter; pending: number }) {
  const { t } = useTranslation()
  const tab = (name: UsersFilter) =>
    cn(
      '-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium',
      filter === name
        ? 'border-primary text-foreground'
        : 'border-transparent text-muted-foreground hover:text-foreground',
    )
  return (
    <nav aria-label={t('users.views')} className="mb-4 flex border-b">
      <Link
        to="/admin/users"
        search={{}}
        className={tab('all')}
        aria-current={filter === 'all' ? 'page' : undefined}
      >
        {t('users.allTab')}
      </Link>
      <Link
        to="/admin/users"
        search={{ filter: 'pending' }}
        className={tab('pending')}
        aria-current={filter === 'pending' ? 'page' : undefined}
      >
        {t('users.pending.tab')}
        {pending > 0 && (
          <Badge aria-label={t('users.pending.count', { count: pending })}>
            {badgeCount(pending)}
          </Badge>
        )}
      </Link>
    </nav>
  )
}
