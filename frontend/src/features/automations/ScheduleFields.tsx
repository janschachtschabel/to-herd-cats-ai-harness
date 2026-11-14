import { useId, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Field } from '@/features/shared/forms'
import type { AutomationValues, FieldErrors, Kind } from './form'
import { cronOf, MAX_MONTH_DAY, PRESET_KINDS, WEEKDAYS, type Preset } from './schedule'
import { timeZones } from './zoned'

type Change = (patch: Partial<AutomationValues>) => void

/** The kind, chosen once (it cannot change after creation). */
export function KindField({
  kinds,
  value,
  onChange,
}: {
  kinds: readonly Kind[]
  value: Kind
  onChange: (kind: Kind) => void
}) {
  const { t } = useTranslation()
  const name = useId()
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-sm font-medium">{t('automations.form.kind')}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {kinds.map((kind) => (
          <label
            key={kind}
            className="flex cursor-pointer items-start gap-2 rounded-lg border p-2 text-sm has-checked:border-primary has-checked:bg-primary/5"
          >
            <input
              type="radio"
              name={name}
              value={kind}
              checked={value === kind}
              onChange={() => onChange(kind)}
              className="mt-0.5 size-4 shrink-0 accent-primary"
            />
            <span>
              <span className="font-medium">{t(`automations.kinds.${kind}`)}</span>
              <span className="block text-xs text-muted-foreground">
                {t(`automations.kindHints.${kind}`)}
              </span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

export function ZoneField({
  value,
  error,
  onChange,
}: {
  value: string
  error?: string
  onChange: Change
}) {
  const { t } = useTranslation()
  const zones = useMemo(() => timeZones(), [])
  return (
    <Field label={t('automations.form.zone')} error={error}>
      {(props) => (
        <NativeSelect {...props} value={value} onChange={(e) => onChange({ zone: e.target.value })}>
          {!zones.includes(value) && <option value={value}>{value}</option>}
          {zones.map((zone) => (
            <option key={zone} value={zone}>
              {zone}
            </option>
          ))}
        </NativeSelect>
      )}
    </Field>
  )
}

/** A `once`: a date and a time in a zone. */
export function OnceFields({
  values,
  errors,
  onChange,
}: {
  values: AutomationValues
  errors: FieldErrors
  onChange: Change
}) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('automations.form.date')} error={errors.once}>
          {(props) => (
            <Input
              {...props}
              type="date"
              value={values.onceDate}
              onChange={(e) => onChange({ onceDate: e.target.value })}
            />
          )}
        </Field>
        <Field label={t('automations.form.time')}>
          {(props) => (
            <Input
              {...props}
              type="time"
              value={values.onceTime}
              onChange={(e) => onChange({ onceTime: e.target.value })}
            />
          )}
        </Field>
      </div>
      <ZoneField value={values.zone} error={errors.zone} onChange={onChange} />
    </div>
  )
}

/** A recurring one: a preset that writes the cron, or the cron itself (expert field). */
export function RecurringFields({
  values,
  errors,
  onChange,
}: {
  values: AutomationValues
  errors: FieldErrors
  onChange: Change
}) {
  const { t } = useTranslation()
  const preset = values.preset
  const set = (patch: Partial<Preset>) => onChange({ preset: { ...preset, ...patch } })
  return (
    <div className="flex flex-col gap-3">
      <Field label={t('automations.form.preset')}>
        {(props) => (
          <NativeSelect
            {...props}
            value={preset.kind}
            onChange={(e) => {
              const kind = e.target.value as Preset['kind']
              // The expert field starts from the cron the preset wrote.
              set(kind === 'custom' ? { kind, cron: cronOf(preset) ?? preset.cron } : { kind })
            }}
          >
            {PRESET_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {t(`automations.form.presets.${kind}`)}
              </option>
            ))}
          </NativeSelect>
        )}
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        {preset.kind === 'hourly' && (
          <Field label={t('automations.form.minute')} error={errors.cron}>
            {(props) => (
              <Input
                {...props}
                type="number"
                min={0}
                max={59}
                value={String(preset.minute)}
                onChange={(e) =>
                  set({ minute: e.target.value === '' ? NaN : Number(e.target.value) })
                }
              />
            )}
          </Field>
        )}
        {preset.kind === 'weekly' && (
          <Field label={t('automations.form.weekday')}>
            {(props) => (
              <NativeSelect
                {...props}
                value={String(preset.weekday)}
                onChange={(e) => set({ weekday: Number(e.target.value) })}
              >
                {WEEKDAYS.map((day) => (
                  <option key={day} value={day}>
                    {t(`automations.weekdays.${day}`)}
                  </option>
                ))}
              </NativeSelect>
            )}
          </Field>
        )}
        {preset.kind === 'monthly' && (
          <Field label={t('automations.form.monthDay')} hint={t('automations.form.monthDayHint')}>
            {(props) => (
              <Input
                {...props}
                type="number"
                min={1}
                max={MAX_MONTH_DAY}
                value={String(preset.monthDay)}
                onChange={(e) => set({ monthDay: Number(e.target.value) })}
              />
            )}
          </Field>
        )}
        {preset.kind !== 'hourly' && preset.kind !== 'custom' && (
          <Field label={t('automations.form.time')} error={errors.cron}>
            {(props) => (
              <Input
                {...props}
                type="time"
                value={preset.time}
                onChange={(e) => set({ time: e.target.value })}
              />
            )}
          </Field>
        )}
      </div>
      {preset.kind === 'custom' && (
        <Field
          label={t('automations.form.cron')}
          hint={t('automations.form.cronHint')}
          error={errors.cron}
        >
          {(props) => (
            <Input
              {...props}
              className="font-mono"
              autoComplete="off"
              spellCheck={false}
              value={preset.cron}
              onChange={(e) => set({ cron: e.target.value })}
            />
          )}
        </Field>
      )}
      <ZoneField value={values.zone} error={errors.zone} onChange={onChange} />
    </div>
  )
}
