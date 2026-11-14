import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { useWiki } from '@/features/wiki/WikiContext'
import { ticketAbilities } from '../abilities'
import { CreateSprintDialog } from './CreateSprintDialog'
import { useSprints } from './queries'
import { SprintItem } from './SprintItem'

/** A space's sprints (`/spaces/<id>/sprints`): the running one, the planned ones and
 *  the closed ones with their tally. With `ticket.assign` they are made, started and
 *  closed here; tickets go into them from the backlog or the ticket. */
export function SprintsView() {
  const { t } = useTranslation()
  const { space } = useWiki()
  const abilities = ticketAbilities(space.my_role)
  const sprints = useSprints(space.id)
  const [creating, setCreating] = useState(false)
  return (
    <section aria-labelledby="sprints-title" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 id="sprints-title" className="text-base font-semibold">
            {t('tickets.sprints.title')}
          </h2>
          <p className="text-sm text-muted-foreground">{t('tickets.sprints.description')}</p>
        </div>
        {abilities.manageSprints && (
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden />
            {t('tickets.sprints.create')}
          </Button>
        )}
      </div>
      {sprints.isPending ? (
        <LoadingState rows={3} />
      ) : sprints.isError ? (
        <ErrorState error={sprints.error} onRetry={() => void sprints.refetch()} />
      ) : sprints.items.length === 0 ? (
        <EmptyState text={t('tickets.sprints.empty')} />
      ) : (
        <ul className="flex flex-col gap-3">
          {sprints.items.map((sprint) => (
            <li key={sprint.id}>
              <SprintItem sprint={sprint} sprints={sprints.items} abilities={abilities} />
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={sprints.hasMore} loading={sprints.loadingMore} onLoad={sprints.loadMore} />
      {abilities.manageSprints && (
        <CreateSprintDialog spaceId={space.id} open={creating} onOpenChange={setCreating} />
      )}
    </section>
  )
}
