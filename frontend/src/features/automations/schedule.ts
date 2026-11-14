/** Presets for a recurring automation's cron (the API takes only the cron string, five
 *  fields, in the automation's zone): what people mostly want, without writing cron.
 *  `presetOf` reads back exactly the forms `cronOf` writes; anything else is the
 *  expert field's (`custom`). Weekdays are ISO (1 = Monday … 7 = Sunday). */

export const PRESET_KINDS = ['hourly', 'daily', 'weekdays', 'weekly', 'monthly', 'custom'] as const
export type PresetKind = (typeof PRESET_KINDS)[number]

export interface Preset {
  kind: PresetKind
  /** The minute of an hourly one (0–59). */
  minute: number
  /** "HH:MM" of the others. */
  time: string
  /** ISO weekday of a weekly one. */
  weekday: number
  /** Day of the month of a monthly one (1–28, so every month has it). */
  monthDay: number
  /** The expert field. */
  cron: string
}

export const DEFAULT_PRESET: Preset = {
  kind: 'daily',
  minute: 0,
  time: '09:00',
  weekday: 1,
  monthDay: 1,
  cron: '0 9 * * *',
}

export const MAX_MONTH_DAY = 28

const TIME = /^([01]\d|2[0-3]):([0-5]\d)$/

function hourMinute(time: string): [number, number] | null {
  const match = TIME.exec(time)
  return match ? [Number(match[1]), Number(match[2])] : null
}

function two(n: number): string {
  return String(n).padStart(2, '0')
}

/** The cron of a preset; null while a field is not valid yet. */
export function cronOf(preset: Preset): string | null {
  if (preset.kind === 'custom') return preset.cron.trim() || null
  if (preset.kind === 'hourly') {
    const ok = Number.isInteger(preset.minute) && preset.minute >= 0 && preset.minute <= 59
    return ok ? `${preset.minute} * * * *` : null
  }
  const hm = hourMinute(preset.time)
  if (!hm) return null
  const [h, m] = hm
  switch (preset.kind) {
    case 'daily':
      return `${m} ${h} * * *`
    case 'weekdays':
      return `${m} ${h} * * 1-5`
    case 'weekly':
      return preset.weekday >= 1 && preset.weekday <= 7
        ? `${m} ${h} * * ${preset.weekday % 7}`
        : null
    case 'monthly':
      return preset.monthDay >= 1 && preset.monthDay <= MAX_MONTH_DAY
        ? `${m} ${h} ${preset.monthDay} * *`
        : null
  }
}

const NUMBER = /^\d{1,2}$/

function num(field: string, max: number, min = 0): number | null {
  if (!NUMBER.test(field)) return null
  const n = Number(field)
  return n >= min && n <= max ? n : null
}

/** The preset a stored cron came from (the expert field for anything else). */
export function presetOf(cron: string): Preset {
  const fields = cron.trim().split(/\s+/)
  const custom: Preset = { ...DEFAULT_PRESET, kind: 'custom', cron: cron.trim() }
  if (fields.length !== 5) return custom
  const [mi, h, dom, mon, dow] = fields as [string, string, string, string, string]
  const minute = num(mi, 59)
  if (minute === null || mon !== '*') return custom
  const base = { ...DEFAULT_PRESET, cron: cron.trim(), minute }
  if (h === '*' && dom === '*' && dow === '*') return { ...base, kind: 'hourly' }
  const hour = num(h, 23)
  if (hour === null) return custom
  const time = `${two(hour)}:${two(minute)}`
  if (dom === '*' && dow === '*') return { ...base, kind: 'daily', time }
  if (dom === '*' && dow === '1-5') return { ...base, kind: 'weekdays', time }
  const day = dom === '*' ? num(dow, 7) : null
  if (day !== null) return { ...base, kind: 'weekly', time, weekday: day === 0 ? 7 : day }
  const monthDay = dow === '*' ? num(dom, MAX_MONTH_DAY, 1) : null
  if (monthDay !== null) return { ...base, kind: 'monthly', time, monthDay }
  return custom
}
