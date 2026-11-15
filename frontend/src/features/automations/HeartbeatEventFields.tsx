import { useQuery } from '@tanstack/react-query'
import { Info } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Field } from '@/features/shared/forms'
import { spaceTagsQuery } from '@/features/wiki/tags/queries'
import type { Schemas } from '@/lib/api'
import { INTERVAL_MINUTES, QUIET_MINUTES, type AutomationValues, type FieldErrors } from './form'
import { WEEKDAYS } from './schedule'
import { ZoneField } from './ScheduleFields'

type Change = (patch: Partial<AutomationValues>) => void

const EVENT_TYPES: readonly Schemas['EventType'][] = [
  'ticket.created',
  'page.published',
  'attachment.uploaded',
  'page.review_due',
]
const TICKET_KINDS: readonly Schemas['TicketKind'][] = ['epic', 'story', 'task', 'bug']

export function Hint({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-start gap-2 rounded-lg border border-sky-300 bg-sky-50 p-2 text-sm text-sky-950 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-100">
      <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  )
}

/** A heartbeat: its interval, the active weekdays and hours in a zone; an answer of
 *  exactly HEARTBEAT_OK stays silent (said here). */
export function HeartbeatFields({
  values,
  errors,
  onChange,
}: {
  values: AutomationValues
  errors: FieldErrors
  onChange: Change
}) {
  const { t } = useTranslation()
  const toggle = (day: number) =>
    onChange({
      days: values.days.includes(day)
        ? values.days.filter((d) => d !== day)
        : [...values.days, day],
    })
  return (
    <div className="flex flex-col gap-3">
      <Hint>{t('automations.form.heartbeatOk')}</Hint>
      <Field
        label={t('automations.form.interval')}
        hint={t('automations.form.intervalHint')}
        error={errors.interval}
      >
        {(props) => (
          <Input
            {...props}
            type="number"
            min={INTERVAL_MINUTES.min}
            max={INTERVAL_MINUTES.max}
            value={values.interval}
            onChange={(e) => onChange({ interval: e.target.value })}
          />
        )}
      </Field>
      <fieldset aria-describedby={errors.days ? 'heartbeat-days-error' : undefined}>
        <legend className="mb-1 text-sm font-medium">{t('automations.form.days')}</legend>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {WEEKDAYS.map((day) => (
            <label key={day} className="flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                checked={values.days.includes(day)}
                onChange={() => toggle(day)}
                className="size-4 accent-primary"
                aria-label={t(`automations.weekdays.${day}`)}
              />
              <span aria-hidden>{t(`automations.weekdaysShort.${day}`)}</span>
            </label>
          ))}
        </div>
        {errors.days && (
          <p id="heartbeat-days-error" className="mt-1 text-xs text-destructive">
            {errors.days}
          </p>
        )}
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('automations.form.from')}>
          {(props) => (
            <Input
              {...props}
              type="time"
              value={values.from}
              onChange={(e) => onChange({ from: e.target.value })}
            />
          )}
        </Field>
        <Field label={t('automations.form.until')}>
          {(props) => (
            <Input
              {...props}
              type="time"
              value={values.until}
              onChange={(e) => onChange({ until: e.target.value })}
            />
          )}
        </Field>
      </div>
      <p className="text-xs text-muted-foreground">{t('automations.form.hoursHint')}</p>
      <ZoneField value={values.zone} error={errors.zone} onChange={onChange} />
    </div>
  )
}

/** An event rule (managers of the space): the event, for `ticket.created` a tag and a
 *  kind, the quiet time; and what the run may do and read. */
export function EventFields({
  values,
  errors,
  onChange,
  spaceId,
}: {
  values: AutomationValues
  errors: FieldErrors
  onChange: Change
  spaceId: string
}) {
  const { t } = useTranslation()
  const tags = useQuery(spaceTagsQuery(spaceId))
  const filters = values.eventType === 'ticket.created'
  return (
    <div className="flex flex-col gap-3">
      <Hint>{t('automations.form.eventRights')}</Hint>
      <Hint>{t('automations.form.eventSight')}</Hint>
      <Field label={t('automations.form.event')}>
        {(props) => (
          <NativeSelect
            {...props}
            value={values.eventType}
            onChange={(e) => onChange({ eventType: e.target.value as Schemas['EventType'] })}
          >
            {EVENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {t(`automations.events.${type.replace('.', '_')}`)}
              </option>
            ))}
          </NativeSelect>
        )}
      </Field>
      {filters && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t('automations.form.tag')}>
            {(props) => (
              <NativeSelect
                {...props}
                value={values.tagId}
                onChange={(e) => onChange({ tagId: e.target.value })}
              >
                <option value="">{t('automations.form.anyTag')}</option>
                {(tags.data ?? []).map((tag) => (
                  <option key={tag.id} value={tag.id}>
                    {tag.name}
                  </option>
                ))}
              </NativeSelect>
            )}
          </Field>
          <Field label={t('automations.form.ticketKind')}>
            {(props) => (
              <NativeSelect
                {...props}
                value={values.ticketKind}
                onChange={(e) =>
                  onChange({ ticketKind: e.target.value as AutomationValues['ticketKind'] })
                }
              >
                <option value="">{t('automations.form.anyKind')}</option>
                {TICKET_KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {t(`tickets.kinds.${kind}`)}
                  </option>
                ))}
              </NativeSelect>
            )}
          </Field>
        </div>
      )}
      <Field
        label={t('automations.form.quiet')}
        hint={t('automations.form.quietHint')}
        error={errors.quiet}
      >
        {(props) => (
          <Input
            {...props}
            type="number"
            min={QUIET_MINUTES.min}
            max={QUIET_MINUTES.max}
            value={values.quietMinutes}
            onChange={(e) => onChange({ quietMinutes: e.target.value })}
          />
        )}
      </Field>
    </div>
  )
}
