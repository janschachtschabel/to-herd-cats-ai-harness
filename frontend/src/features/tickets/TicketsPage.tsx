import { Plus } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { useSidebarSpaces } from '@/features/spaces/queries'
import { cn } from '@/lib/utils'
import { ticketAbilities } from './abilities'
import { CreateTicketDialog } from './CreateTicketDialog'
import { isMine, type TicketSearch } from './filters'
import { useTickets } from './queries'
import { TicketFilters } from './TicketFilters'
import { TicketRows } from './TicketRows'

/** The tickets one may see across spaces (`/tickets`). Without filters it shows "my
 *  tickets": assigned to me and not finished. Every filter stands in the address. */
export function TicketsPage({
  search,
  onSearch,
}: {
  search: TicketSearch
  onSearch: (next: TicketSearch) => void
}) {
  const { t } = useTranslation()
  const tickets = useTickets(search)
  const spaces = useSidebarSpaces()
  const [creating, setCreating] = useState(false)
  const creatable = spaces.items.filter((space) => ticketAbilities(space.my_role).create)
  const names = useMemo(() => new Map(spaces.items.map((s) => [s.id, s.name])), [spaces.items])
  const mine = isMine(search)

  const tab = (active: boolean, label: string, next: TicketSearch) => (
    <button
      type="button"
      aria-pressed={active}
      onClick={() => onSearch(next)}
      className={cn(
        'border-b-2 px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
        active
          ? 'border-primary font-medium'
          : 'border-transparent text-muted-foreground hover:text-foreground',
      )}
    >
      {label}
    </button>
  )

  return (
    <div>
      <PageHeader
        title={t('tickets.title')}
        description={mine ? t('tickets.list.mineDescription') : t('tickets.list.allDescription')}
        actions={
          creatable.length > 0 && (
            <Button onClick={() => setCreating(true)}>
              <Plus aria-hidden />
              {t('tickets.create.open')}
            </Button>
          )
        }
      />
      <div className="mb-4 flex gap-1 border-b" role="group" aria-label={t('tickets.list.views')}>
        {tab(mine, t('tickets.list.mine'), { ...search, who: undefined })}
        {tab(!mine, t('tickets.list.all'), { ...search, who: 'all' })}
      </div>
      <TicketFilters search={search} spaces={spaces.items} onChange={onSearch} />
      {tickets.isPending ? (
        <LoadingState />
      ) : tickets.isError ? (
        <ErrorState error={tickets.error} onRetry={() => void tickets.refetch()} />
      ) : tickets.items.length === 0 ? (
        <EmptyState text={mine ? t('tickets.list.emptyMine') : t('tickets.list.empty')} />
      ) : (
        <TicketRows tickets={tickets.items} spaceNames={names} />
      )}
      <LoadMore hasMore={tickets.hasMore} loading={tickets.loadingMore} onLoad={tickets.loadMore} />
      {creatable.length > 0 && (
        <CreateTicketDialog open={creating} onOpenChange={setCreating} spaces={creatable} />
      )}
    </div>
  )
}
