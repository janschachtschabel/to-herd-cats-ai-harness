import { Link } from '@tanstack/react-router'
import { AlertTriangle, ArrowLeft, PauseCircle, Pencil } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AgentBadge } from '@/features/agents/AgentBadge'
import { EmptyState, ErrorState, LoadingState, PageHeader } from '@/features/shared/states'
import { ApiError } from '@/lib/api'
import { AutomationActions } from './AutomationActions'
import { AutomationFormDialog } from './AutomationFormDialog'
import { LastRun, NextTerm } from './AutomationList'
import { agentName, placeText, scheduleText, stateText, termText, titleText } from './display'
import { FiringLog } from './FiringLog'
import { useAutomation, type Automation } from './queries'

/** One automation, as its route shows it; one the reader may not see (or that is
 *  gone) says so in words, as the API answers 404 for both. */
export function AutomationScreen({ automationId }: { automationId: string }) {
  const { t } = useTranslation()
  const automation = useAutomation(automationId)
  if (automation.isPending) return <LoadingState />
  if (automation.isError) {
    if (automation.error instanceof ApiError && automation.error.status === 404) {
      return <EmptyState text={t('automations.detail.notFound')} />
    }
    return <ErrorState error={automation.error} onRetry={() => void automation.refetch()} />
  }
  return <AutomationDetail automation={automation.data} />
}

function PlaceLink({ automation }: { automation: Automation }) {
  const { t } = useTranslation()
  const place = automation.place
  const className = 'underline-offset-2 hover:underline'
  if (automation.redacted) return <span>{placeText(t, automation)}</span>
  if (place.type === 'ticket' && place.ticket_number) {
    return (
      <Link
        to="/tickets/$number"
        params={{ number: String(place.ticket_number) }}
        className={className}
      >
        {placeText(t, automation)}
      </Link>
    )
  }
  return (
    <Link
      to="/c/$conversationId"
      params={{ conversationId: place.conversation_id }}
      className={className}
    >
      {placeText(t, automation)}
    </Link>
  )
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </>
  )
}

/** Its owner changes it in the form (its kind stays). */
function EditAutomation({ automation }: { automation: Automation }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        <Pencil aria-hidden />
        {t('automations.actions.edit')}
      </Button>
      <AutomationFormDialog open={open} onOpenChange={setOpen} automation={automation} />
    </>
  )
}

function AutomationDetail({ automation }: { automation: Automation }) {
  const { t, i18n } = useTranslation()
  const paused = automation.state === 'paused'
  const ownerUnable = paused && automation.paused_reason === 'owner' && !automation.abilities.resume
  const heartbeat = automation.kind === 'heartbeat'
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={titleText(t, automation)}
        actions={
          <Button variant="outline" asChild>
            <Link to="/automations">
              <ArrowLeft aria-hidden />
              {t('automations.detail.back')}
            </Link>
          </Button>
        }
      >
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge variant="outline">{t(`automations.kinds.${automation.kind}`)}</Badge>
          {!paused && <Badge variant="secondary">{stateText(t, automation)}</Badge>}
        </div>
      </PageHeader>
      {paused && (
        <div className="flex flex-col gap-1 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100">
          <p className="flex items-start gap-1.5 font-medium">
            <PauseCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
            {stateText(t, automation)}
          </p>
          {ownerUnable && <p>{t('automations.takeOver.ownerUnable')}</p>}
        </div>
      )}
      {automation.term_errors > 0 && (
        <p className="flex items-start gap-1.5 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          {t('automations.detail.termErrors', { count: automation.term_errors })}
        </p>
      )}
      <AutomationActions
        automation={automation}
        edit={automation.abilities.edit ? <EditAutomation automation={automation} /> : undefined}
      />
      <section aria-labelledby="automation-instruction" className="flex flex-col gap-2">
        <h2 id="automation-instruction" className="text-base font-semibold">
          {t(heartbeat ? 'automations.detail.checklist' : 'automations.detail.instruction')}
        </h2>
        {automation.instruction === null ? (
          <p className="text-sm text-muted-foreground">{t('automations.redacted.instruction')}</p>
        ) : (
          <p className="rounded-lg border bg-muted/30 p-3 text-sm whitespace-pre-wrap">
            {automation.instruction}
          </p>
        )}
      </section>
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
        <Fact label={t('automations.detail.agent')}>
          <span className="inline-flex items-center gap-1">
            {agentName(t, automation)} <AgentBadge of="agent" />
          </span>
        </Fact>
        <Fact label={t('automations.detail.owner')}>
          {automation.owner.name ?? t('automations.list.unknownOwner')}
        </Fact>
        <Fact label={t('automations.detail.place')}>
          <PlaceLink automation={automation} />
        </Fact>
        <Fact label={t('automations.detail.schedule')}>
          <span className="flex flex-col">
            <span>{scheduleText(t, automation, i18n.language)}</span>
            {automation.time_zone && (
              <span className="text-muted-foreground">
                {t('automations.schedule.zone', { zone: automation.time_zone })}
              </span>
            )}
            {automation.kind === 'event' && <EventDetails automation={automation} />}
          </span>
        </Fact>
        {automation.kind !== 'event' && (
          <Fact label={t('automations.detail.next')}>
            <NextTerm automation={automation} />
          </Fact>
        )}
        <Fact label={t('automations.detail.lastRun')}>
          <LastRun automation={automation} />
        </Fact>
      </dl>
      {automation.upcoming.length > 0 && (
        <section aria-labelledby="automation-upcoming" className="flex flex-col gap-2">
          <h2 id="automation-upcoming" className="text-base font-semibold">
            {t('automations.detail.upcoming')}
          </h2>
          <ul
            aria-labelledby="automation-upcoming"
            className="flex flex-col gap-1 text-sm tabular-nums"
          >
            {automation.upcoming.map((term) => (
              <li key={term}>
                <time dateTime={term}>
                  {termText(t, term, i18n.language, automation.time_zone)}
                </time>
              </li>
            ))}
          </ul>
        </section>
      )}
      <FiringLog automationId={automation.id} />
    </div>
  )
}

function EventDetails({ automation }: { automation: Automation }) {
  const { t } = useTranslation()
  const minutes = Math.round((automation.quiet_seconds ?? 0) / 60)
  return (
    <span className="text-muted-foreground">
      {t('automations.detail.quiet', { count: minutes })}
      {automation.filter_ticket_kind &&
        ` · ${t('automations.detail.filterKind', { kind: t(`tickets.kinds.${automation.filter_ticket_kind}`) })}`}
      {automation.filter_tag_id && ` · ${t('automations.detail.filterTag')}`}
    </span>
  )
}
