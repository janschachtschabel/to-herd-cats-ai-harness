import type { TFunction } from 'i18next'
import { ticketKey } from '@/features/tickets/refs'
import type { Automation, Firing } from './queries'
import { presetOf } from './schedule'
import { formatTerm, viewerZone } from './zoned'

/** An automation in words: where it reports, when it runs, how it stands, how a term
 *  went. Nothing here decides what one may do (that is `abilities` from the API). */

export const EXCERPT_CHARS = 140

/** The first line of its instruction, cut to a list's width. */
export function excerpt(instruction: string): string {
  const line = instruction.trim().split('\n')[0] ?? ''
  return line.length > EXCERPT_CHARS ? `${line.slice(0, EXCERPT_CHARS - 1)}…` : line
}

/** Its title: the instruction's first line, or (withheld from the reader, `redacted`)
 *  whose agent it is. */
export function titleText(t: TFunction, automation: Automation): string {
  return automation.instruction === null
    ? t('automations.redacted.title', { agent: agentName(t, automation) })
    : excerpt(automation.instruction)
}

export function agentName(t: TFunction, automation: Automation): string {
  return automation.agent.name ?? t('automations.list.unknownAgent')
}

export function placeText(t: TFunction, automation: Automation): string {
  const place = automation.place
  if (place.type === 'dm') return t('automations.place.dm', { agent: agentName(t, automation) })
  if (automation.redacted) return t(`automations.redacted.${place.type}`)
  if (place.type === 'ticket') {
    return t('automations.place.ticket', { key: ticketKey(place.ticket_number ?? 0) })
  }
  return place.name
    ? t('automations.place.channel', { name: place.name })
    : t('automations.place.unnamed')
}

/** "Täglich um 09:00", "Alle 30 Minuten, Mo–Fr, 09:00–17:00", "Bei: Ticket angelegt". */
export function scheduleText(t: TFunction, automation: Automation, locale: string): string {
  switch (automation.kind) {
    case 'once': {
      const at = automation.next_due_at ?? automation.last_run?.due_at
      return at ? t('automations.schedule.once', { at: termText(t, at, locale, null) }) : ''
    }
    case 'recurring': {
      const preset = presetOf(automation.cron ?? '')
      const day = preset.kind === 'weekly' ? t(`automations.weekdays.${preset.weekday}`) : ''
      return t(`automations.schedule.${preset.kind}`, {
        minute: String(preset.minute).padStart(2, '0'),
        time: preset.time,
        day: preset.kind === 'monthly' ? preset.monthDay : day,
        cron: preset.cron,
      })
    }
    case 'heartbeat':
      return t('automations.schedule.heartbeat', {
        count: automation.interval_minutes ?? 0,
        days: daysText(t, automation.active_days ?? []),
        from: (automation.active_from ?? '').slice(0, 5),
        until: (automation.active_until ?? '').slice(0, 5),
      })
    case 'event':
      return t('automations.schedule.event', { event: eventText(t, automation.event_type) })
  }
}

export function eventText(t: TFunction, eventType: string | null): string {
  return eventType ? t(`automations.events.${eventType.replace('.', '_')}`) : ''
}

/** "Mo–Fr", "Mo, Mi, Fr": runs of three or more days joined with a dash. */
export function daysText(t: TFunction, days: readonly number[]): string {
  const sorted = [...new Set(days)].sort((a, b) => a - b)
  const parts: string[] = []
  for (let i = 0; i < sorted.length;) {
    let j = i
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j]! + 1) j++
    const short = (d: number) => t(`automations.weekdaysShort.${d}`)
    if (j - i >= 2) parts.push(`${short(sorted[i]!)}–${short(sorted[j]!)}`)
    else for (let k = i; k <= j; k++) parts.push(short(sorted[k]!))
    i = j + 1
  }
  return parts.join(', ')
}

/** A term in the reader's time, with the automation's zone named where it differs. */
export function termText(
  t: TFunction,
  iso: string,
  locale: string,
  zone: string | null,
  nameZone = false,
): string {
  const { local, there } = formatTerm(iso, locale, viewerZone(), zone)
  if (there) return `${local} (${t('automations.term.there', { time: there, zone })})`
  return nameZone && zone ? `${local} (${t('automations.term.zone', { zone })})` : local
}

/** Its state in words, with the reason it is paused. */
export function stateText(t: TFunction, automation: Automation): string {
  if (automation.state === 'paused' && automation.paused_reason) {
    return t(`automations.paused.${automation.paused_reason}`)
  }
  return t(`automations.states.${automation.state === 'deleted' ? 'done' : automation.state}`)
}

/** How a term went: started (a heartbeat with nothing to report says so) or why not. */
export function outcomeText(t: TFunction, firing: Pick<Firing, 'outcome' | 'heartbeat_ok'>) {
  if (firing.outcome === 'started' && firing.heartbeat_ok) {
    return t('automations.outcomes.heartbeatOk')
  }
  return t(`automations.outcomes.${firing.outcome}`)
}
