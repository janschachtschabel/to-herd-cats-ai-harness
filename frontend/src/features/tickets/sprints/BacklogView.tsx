import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { useWiki } from '@/features/wiki/WikiContext'
import { errorMessage } from '@/lib/errors'
import { ticketAbilities } from '../abilities'
import { TicketRows } from '../TicketRows'
import { openSprints, usePutIntoSprint, useSprintChoices, useSprintTickets } from './queries'
import { defaultTarget } from './rules'
import { SprintOption } from './SprintOption'

/** A space's backlog (`/spaces/<id>/backlog`): its unfinished tickets in no sprint, by
 *  priority. With `ticket.edit` tickets are picked (checkboxes: Tab and Space) and put
 *  into the running or a planned sprint, each with the version the list showed. */
export function BacklogView() {
  const { t } = useTranslation()
  const { space } = useWiki()
  const abilities = ticketAbilities(space.my_role)
  const tickets = useSprintTickets(space.id, 'none', true)
  const choices = useSprintChoices(space.id, abilities.edit)
  const targets = openSprints(choices.data)
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [chosen, setChosen] = useState<string | null>(null)
  const target = targets.find((s) => s.id === chosen) ?? defaultTarget(targets)
  const put = usePutIntoSprint()
  const selected = tickets.items.filter((ticket) => picked.has(ticket.id))
  const allPicked = tickets.items.length > 0 && selected.length === tickets.items.length

  const toggle = (id: string) =>
    setPicked((before) => {
      const next = new Set(before)
      if (!next.delete(id)) next.add(id)
      return next
    })
  const submit = () => {
    if (!target || selected.length === 0) return
    put.mutate(
      { tickets: selected, sprintId: target.id },
      { onSuccess: () => setPicked(new Set()) },
    )
  }
  const result = put.data
  return (
    <section aria-labelledby="backlog-title" className="flex flex-col gap-4">
      <div>
        <h2 id="backlog-title" className="text-base font-semibold">
          {t('tickets.backlog.title')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('tickets.backlog.description')}</p>
      </div>
      {abilities.edit && tickets.items.length > 0 && (
        <div
          className="flex flex-wrap items-end gap-3 rounded-lg border bg-muted/40 p-3"
          role="group"
          aria-label={t('tickets.backlog.selection')}
        >
          <label className="flex items-center gap-2 pb-1.5 text-sm">
            <input
              type="checkbox"
              className="accent-primary"
              checked={allPicked}
              onChange={() =>
                setPicked(allPicked ? new Set() : new Set(tickets.items.map((x) => x.id)))
              }
            />
            {t('tickets.backlog.selectAll')}
          </label>
          {targets.length > 0 ? (
            <>
              <label className="flex min-w-44 flex-1 flex-col gap-1 text-xs text-muted-foreground sm:flex-none">
                {t('tickets.backlog.target')}
                <NativeSelect value={target?.id ?? ''} onChange={(e) => setChosen(e.target.value)}>
                  {targets.map((sprint) => (
                    <SprintOption key={sprint.id} sprint={sprint} />
                  ))}
                </NativeSelect>
              </label>
              <Button disabled={selected.length === 0 || put.isPending} onClick={submit}>
                {t('tickets.backlog.put', { n: selected.length })}
              </Button>
            </>
          ) : (
            <p className="pb-1.5 text-sm text-muted-foreground">
              {t('tickets.backlog.noSprint')}{' '}
              <Link
                to="/spaces/$spaceId/sprints"
                params={{ spaceId: space.id }}
                className="underline"
              >
                {t('tickets.space.sprints')}
              </Link>
            </p>
          )}
        </div>
      )}
      {result && result.moved > 0 && (
        <p role="status" className="text-sm">
          {t('tickets.backlog.done', {
            count: result.moved,
            name: targets.find((s) => s.id === put.variables?.sprintId)?.name ?? '',
          })}
        </p>
      )}
      {result && (result.stale > 0 || result.failed > 0) && (
        <p
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/5 p-2 text-sm"
        >
          {result.stale > 0 && t('tickets.backlog.stale', { count: result.stale })}{' '}
          {result.failed > 0 && errorMessage(t, result.error)}
        </p>
      )}
      {tickets.isPending ? (
        <LoadingState />
      ) : tickets.isError ? (
        <ErrorState error={tickets.error} onRetry={() => void tickets.refetch()} />
      ) : tickets.items.length === 0 ? (
        <EmptyState text={t('tickets.backlog.empty')} />
      ) : (
        <TicketRows
          tickets={tickets.items}
          lead={
            abilities.edit
              ? (ticket) => (
                  <input
                    type="checkbox"
                    className="size-4 accent-primary"
                    aria-label={t('tickets.backlog.select', { key: ticket.key })}
                    checked={picked.has(ticket.id)}
                    onChange={() => toggle(ticket.id)}
                  />
                )
              : undefined
          }
        />
      )}
      <LoadMore hasMore={tickets.hasMore} loading={tickets.loadingMore} onLoad={tickets.loadMore} />
    </section>
  )
}
