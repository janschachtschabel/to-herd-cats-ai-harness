import { ChevronDown, ChevronRight, Play, Square } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import type { Sprint } from '@/lib/api'
import { formatDay } from '@/lib/format'
import type { TicketAbilities } from '../abilities'
import { CloseSprintDialog } from './CloseSprintDialog'
import { useStartSprint } from './queries'
import { sprintOffers } from './rules'
import { SprintTickets } from './SprintTickets'

const STATE_BADGE = { active: 'default', planned: 'outline', closed: 'secondary' } as const

/** A sprint: name, state, dates, goal; the tally once closed; start or close where
 *  allowed; its tickets on request. */
export function SprintItem({
  sprint,
  sprints,
  abilities,
}: {
  sprint: Sprint
  sprints: Sprint[]
  abilities: TicketAbilities
}) {
  const { t, i18n } = useTranslation()
  const offers = sprintOffers(sprint, sprints, abilities)
  const start = useStartSprint(sprint)
  const [closing, setClosing] = useState(false)
  const [open, setOpen] = useState(false)
  const headingId = `sprint-${sprint.id}`
  const panelId = `sprint-tickets-${sprint.id}`
  return (
    <article aria-labelledby={headingId} className="flex flex-col gap-2 rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-expanded={open}
          aria-controls={panelId}
          aria-label={t('tickets.sprints.toggle', { name: sprint.name })}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <ChevronDown aria-hidden /> : <ChevronRight aria-hidden />}
        </Button>
        <h3 id={headingId} className="min-w-0 truncate text-sm font-semibold">
          {sprint.name}
        </h3>
        <Badge variant={STATE_BADGE[sprint.state]}>
          {t(`tickets.sprints.states.${sprint.state}`)}
        </Badge>
        <span className="text-xs text-muted-foreground">
          {t('tickets.sprints.dates', {
            from: formatDay(sprint.starts_on, i18n.language),
            to: formatDay(sprint.ends_on, i18n.language),
          })}
        </span>
        <div className="ml-auto flex gap-2">
          {offers.start && (
            <Button
              size="sm"
              variant="outline"
              disabled={start.isPending}
              aria-label={t('tickets.sprints.start', { name: sprint.name })}
              onClick={() => start.mutate()}
            >
              <Play aria-hidden />
              {t('tickets.sprints.startShort')}
            </Button>
          )}
          {offers.close && (
            <Button
              size="sm"
              aria-label={t('tickets.sprints.close', { name: sprint.name })}
              onClick={() => setClosing(true)}
            >
              <Square aria-hidden />
              {t('tickets.sprints.closeShort')}
            </Button>
          )}
        </div>
      </div>
      <div className="flex flex-col gap-1 pl-9 text-sm">
        {sprint.goal && <p className="break-words">{sprint.goal}</p>}
        {sprint.tally && (
          <p>
            <span className="text-muted-foreground">{t('tickets.sprints.tallyLabel')} </span>
            <span className="tabular-nums">{t('tickets.sprints.tally', { ...sprint.tally })}</span>
          </p>
        )}
        {offers.blockedBy && (
          <p className="text-xs text-muted-foreground">
            {t('tickets.sprints.startBlocked', { name: offers.blockedBy.name })}
          </p>
        )}
        {start.error ? (
          <p role="alert" className="text-sm text-destructive">
            {errorMessage(t, start.error)}
          </p>
        ) : null}
      </div>
      {open && (
        <div id={panelId} className="pl-9">
          <SprintTickets sprint={sprint} editable={abilities.edit} />
        </div>
      )}
      {offers.close && (
        <CloseSprintDialog
          sprint={sprint}
          sprints={sprints}
          open={closing}
          onOpenChange={setClosing}
        />
      )}
    </article>
  )
}
