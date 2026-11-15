import { components } from '../../../openapi.json'
import type { Schemas } from '@/lib/api'
import i18n from '@/lib/i18n'
import { bodySchema } from '@/lib/schemas'
import type { Automation, ScheduleIn } from './queries'
import { cronOf, DEFAULT_PRESET, presetOf, type Preset } from './schedule'
import { isoToZoned, zonedToIso } from './zoned'

/** The automation form as typed, and what it becomes for the API. Bounds come from
 *  openapi.json (lengths, the quiet time) or are the API's term rules, which the live
 *  preview checks as typed (`automation.too_frequent`, ...). */

export type Kind = Schemas['AutomationKind']
export type PlaceType = 'dm' | 'channel' | 'ticket'
export type EventType = Schemas['EventType']
export type TicketKind = Schemas['TicketKind']

export interface AutomationValues {
  agent: { id: string; name: string } | null
  placeType: PlaceType
  conversationId: string
  ticketNumber: string
  instruction: string
  kind: Kind
  onceDate: string
  onceTime: string
  preset: Preset
  zone: string
  interval: string
  days: number[]
  from: string
  until: string
  eventType: EventType
  tagId: string
  ticketKind: TicketKind | ''
  quietMinutes: string
}

export type Field =
  'agent' | 'place' | 'instruction' | 'once' | 'cron' | 'zone' | 'interval' | 'days' | 'quiet'
export type FieldErrors = Partial<Record<Field, string>>

const QUIET = components.schemas.EventIn.properties.quiet_seconds
export const QUIET_MINUTES = { min: QUIET.minimum / 60, max: QUIET.maximum / 60 }
export const DEFAULT_QUIET_MINUTES = QUIET.default / 60
/** The heartbeat's interval in minutes (the API's term rules, `automation.invalid_interval`). */
export const INTERVAL_MINUTES = { min: 15, max: 1440 }
export const OFFICE_DAYS = [1, 2, 3, 4, 5]

export function newValues({
  zone,
  agent,
  placeType = 'dm',
  conversationId = '',
}: {
  zone: string
  agent: AutomationValues['agent']
  placeType?: PlaceType
  conversationId?: string
}): AutomationValues {
  return {
    agent,
    placeType,
    conversationId,
    ticketNumber: '',
    instruction: '',
    kind: 'recurring',
    onceDate: '',
    onceTime: '09:00',
    preset: DEFAULT_PRESET,
    zone,
    interval: '60',
    days: OFFICE_DAYS,
    from: '09:00',
    until: '17:00',
    eventType: 'ticket.created',
    tagId: '',
    ticketKind: '',
    quietMinutes: String(DEFAULT_QUIET_MINUTES),
  }
}

const hhmm = (time: string | null) => (time ?? '').slice(0, 5)

/** A stored automation in the form (a `once` in the reader's zone: it has none). */
export function valuesOf(automation: Automation, readerZone: string): AutomationValues {
  const zone = automation.time_zone ?? readerZone
  const values = newValues({ zone, agent: automation.agent.id ? toAgent(automation) : null })
  const at = automation.next_due_at ?? automation.last_run?.due_at
  const once = at ? isoToZoned(at, zone) : { date: '', time: '' }
  return {
    ...values,
    placeType: automation.place.type,
    conversationId: automation.place.conversation_id,
    ticketNumber: automation.place.ticket_number ? String(automation.place.ticket_number) : '',
    instruction: automation.instruction ?? '', // only its owner edits it, who reads it
    kind: automation.kind,
    onceDate: once.date,
    onceTime: once.time,
    preset: automation.cron ? presetOf(automation.cron) : values.preset,
    interval: String(automation.interval_minutes ?? values.interval),
    days: automation.active_days ?? values.days,
    from: hhmm(automation.active_from) || values.from,
    until: hhmm(automation.active_until) || values.until,
    eventType: automation.event_type ?? values.eventType,
    tagId: automation.filter_tag_id ?? '',
    ticketKind: automation.filter_ticket_kind ?? '',
    quietMinutes: String((automation.quiet_seconds ?? QUIET.default) / 60),
  }
}

function toAgent(automation: Automation) {
  return { id: automation.agent.id, name: automation.agent.name ?? '' }
}

const wholeNumber = (text: string) => (/^\d+$/.test(text.trim()) ? Number(text.trim()) : NaN)

/** The schedule as typed; null while it is incomplete (no preview, no save). */
export function scheduleOf(values: AutomationValues): ScheduleIn | null {
  switch (values.kind) {
    case 'once': {
      const at = zonedToIso(values.onceDate, values.onceTime, values.zone)
      return at ? { kind: 'once', at } : null
    }
    case 'recurring': {
      const cron = cronOf(values.preset)
      return cron && values.zone ? { kind: 'recurring', cron, time_zone: values.zone } : null
    }
    case 'heartbeat': {
      const interval = wholeNumber(values.interval)
      if (Number.isNaN(interval) || !values.days.length || !values.zone) return null
      if (!values.from || !values.until) return null
      return {
        kind: 'heartbeat',
        interval_minutes: interval,
        active_days: [...values.days].sort((a, b) => a - b),
        active_from: `${values.from}:00`,
        active_until: `${values.until}:00`,
        time_zone: values.zone,
      }
    }
    case 'event': {
      const filters = values.eventType === 'ticket.created'
      return {
        kind: 'event',
        event_type: values.eventType,
        quiet_seconds:
          Math.round(Number(values.quietMinutes.replace(',', '.')) * 60) || QUIET.default,
        filter_tag_id: filters && values.tagId ? values.tagId : null,
        filter_ticket_kind: filters && values.ticketKind ? values.ticketKind : null,
      }
    }
  }
}

const TICKET = /^(?:[A-Za-z]+-)?(\d{1,9})$/

function placeOf(values: AutomationValues): Schemas['AutomationCreate']['place'] {
  if (values.placeType === 'channel') {
    return { type: 'channel', conversation_id: values.conversationId }
  }
  if (values.placeType === 'ticket') {
    const match = TICKET.exec(values.ticketNumber.trim())
    return { type: 'ticket', ticket_number: match ? Number(match[1]) : 0 }
  }
  return { type: 'dm' }
}

export function createBody(values: AutomationValues): Schemas['AutomationCreate'] {
  return {
    agent_id: values.agent?.id ?? '',
    place: placeOf(values),
    instruction: values.instruction,
    schedule: scheduleOf(values)!,
  }
}

/** A change names the version read; the schedule only if it changed (a `once` long
 *  done would be refused as in the past otherwise). The kind stays. */
export function updateBody(
  values: AutomationValues,
  stored: Automation,
): Schemas['AutomationUpdate'] {
  const before = JSON.stringify(scheduleOf(valuesOf(stored, values.zone)))
  const schedule = scheduleOf({ ...values, kind: stored.kind })
  const body: Schemas['AutomationUpdate'] = {
    version: stored.version,
    instruction: values.instruction,
  }
  if (schedule && JSON.stringify(schedule) !== before) body.schedule = schedule
  return body
}

const SCHEMAS = {
  once: 'OnceIn',
  recurring: 'RecurringIn',
  heartbeat: 'HeartbeatIn',
  event: 'EventIn',
} as const

const SCHEDULE_FIELDS: Record<string, Field> = {
  cron: 'cron',
  time_zone: 'zone',
  at: 'once',
  active_days: 'days',
  interval_minutes: 'interval',
}

/** What is missing or out of bounds, by field (empty: ready to save). */
export function checkValues(values: AutomationValues, mode: 'create' | 'edit'): FieldErrors {
  const t = i18n.t.bind(i18n)
  const errors: FieldErrors = {}
  if (mode === 'create') {
    if (!values.agent) errors.agent = t('automations.form.errors.agent')
    if (values.placeType === 'channel' && !values.conversationId) {
      errors.place = t('automations.form.errors.channel')
    }
    if (values.placeType === 'ticket' && !TICKET.test(values.ticketNumber.trim())) {
      errors.place = t('automations.form.errors.ticket')
    }
  }
  const instruction = bodySchema('AutomationUpdate').safeParse({
    version: 0,
    instruction: values.instruction,
  })
  const said = instruction.error?.issues.find((issue) => issue.path[0] === 'instruction')
  if (said) errors.instruction = said.message
  Object.assign(errors, scheduleErrors(values, t))
  return errors
}

function scheduleErrors(values: AutomationValues, t: typeof i18n.t): FieldErrors {
  const errors: FieldErrors = {}
  if (values.kind === 'once' && !scheduleOf(values)) {
    errors.once = t('automations.form.errors.once')
    return errors
  }
  if (values.kind === 'recurring' && !cronOf(values.preset)) {
    errors.cron = t(values.preset.kind === 'custom' ? 'validation.required' : 'validation.invalid')
  }
  if (values.kind === 'heartbeat') {
    const interval = wholeNumber(values.interval)
    if (!(interval >= INTERVAL_MINUTES.min && interval <= INTERVAL_MINUTES.max)) {
      errors.interval = t('automations.form.errors.interval', INTERVAL_MINUTES)
    }
    if (!values.days.length) errors.days = t('automations.form.errors.days')
  }
  if (values.kind === 'event') {
    const quiet = Number(values.quietMinutes.replace(',', '.'))
    if (!(quiet >= QUIET_MINUTES.min && quiet <= QUIET_MINUTES.max)) {
      errors.quiet = t('automations.form.errors.quiet', QUIET_MINUTES)
    }
    return errors
  }
  const schedule = scheduleOf(values)
  if (schedule) {
    const result = bodySchema(SCHEMAS[values.kind]).safeParse(schedule)
    for (const issue of result.error?.issues ?? []) {
      const field = SCHEDULE_FIELDS[String(issue.path[0])]
      if (field) errors[field] ??= issue.message
    }
  } else if (!values.zone) {
    errors.zone = t('validation.required')
  }
  return errors
}
