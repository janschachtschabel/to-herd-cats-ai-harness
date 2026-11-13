import { Link } from '@tanstack/react-router'
import { ChevronDown, ChevronRight, Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { useWiki } from '@/features/wiki/WikiContext'
import type { Epic } from '@/lib/api'
import { ticketAbilities } from '../abilities'
import { CreateTicketDialog } from '../CreateTicketDialog'
import { childTotal } from '../display'
import { StatusBadge } from '../parts'
import { Progress } from '../Progress'
import { useChildren } from '../queries'
import { TicketRows } from '../TicketRows'
import { useEpics } from './queries'

/** A space's epics (`/spaces/<id>/epics`), each with a bar of how far its children
 *  are; an epic opens to show them. */
export function EpicsView() {
  const { t } = useTranslation()
  const { space } = useWiki()
  const abilities = ticketAbilities(space.my_role)
  const epics = useEpics(space.id)
  const [creating, setCreating] = useState(false)
  return (
    <section aria-labelledby="epics-title" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 id="epics-title" className="text-base font-semibold">
          {t('tickets.epics.title')}
        </h2>
        {abilities.create && (
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden />
            {t('tickets.epics.create')}
          </Button>
        )}
      </div>
      {epics.isPending ? (
        <LoadingState rows={3} />
      ) : epics.isError ? (
        <ErrorState error={epics.error} onRetry={() => void epics.refetch()} />
      ) : epics.items.length === 0 ? (
        <EmptyState text={t('tickets.epics.empty')} />
      ) : (
        <ul className="flex flex-col gap-2">
          {epics.items.map((epic) => (
            <EpicItem key={epic.id} epic={epic} />
          ))}
        </ul>
      )}
      <LoadMore hasMore={epics.hasMore} loading={epics.loadingMore} onLoad={epics.loadMore} />
      {abilities.create && (
        <CreateTicketDialog
          open={creating}
          onOpenChange={setCreating}
          spaces={[space]}
          kind="epic"
          onCreated={() => undefined}
        />
      )}
    </section>
  )
}

function EpicItem({ epic }: { epic: Epic }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const total = childTotal(epic.children)
  const children = useChildren(epic.id, open)
  const panelId = `epic-${epic.id}`
  return (
    <li className="rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-expanded={open}
          aria-controls={panelId}
          aria-label={t('tickets.epics.toggle', { key: epic.key })}
          disabled={total === 0}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <ChevronDown aria-hidden /> : <ChevronRight aria-hidden />}
        </Button>
        <Link
          to="/tickets/$number"
          params={{ number: String(epic.number) }}
          className="flex min-w-0 flex-1 items-baseline gap-2 rounded-sm hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <span className="shrink-0 font-mono text-xs text-muted-foreground">{epic.key}</span>{' '}
          <span className="truncate text-sm font-medium">{epic.title}</span>
        </Link>
        <StatusBadge status={epic.status} />
      </div>
      <div className="mt-2 pl-9">
        {total === 0 ? (
          <p className="text-xs text-muted-foreground">{t('tickets.epics.noChildren')}</p>
        ) : (
          <Progress counts={epic.children} />
        )}
      </div>
      {open && (
        <div id={panelId} className="mt-3 pl-9">
          {children.isPending ? (
            <LoadingState rows={2} />
          ) : children.isError ? (
            <ErrorState error={children.error} onRetry={() => void children.refetch()} />
          ) : (
            <TicketRows tickets={children.data.items} />
          )}
        </div>
      )}
    </li>
  )
}
