import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { DirectoryCombobox } from '@/features/directory/DirectoryCombobox'
import { useChannels } from '@/features/messaging/queries'
import { Field } from '@/features/shared/forms'
import { useSidebarSpaces } from '@/features/spaces/queries'
import type { AutomationValues, FieldErrors, PlaceType } from './form'

const NONE = new Set<string>()

type Change = (patch: Partial<AutomationValues>) => void

/** The agent (a picker of the agents I reach). */
export function AgentField({
  values,
  errors,
  onChange,
}: {
  values: AutomationValues
  errors: FieldErrors
  onChange: Change
}) {
  const { t } = useTranslation()
  const selected = values.agent ? { type: 'agent' as const, ...values.agent } : null
  return (
    <Field
      label={t('automations.form.agent')}
      hint={t('automations.form.agentHint')}
      error={errors.agent}
    >
      {(props) => (
        <DirectoryCombobox
          control={props}
          type="agent"
          selected={selected}
          exclude={NONE}
          onSelect={(entry) =>
            onChange({ agent: entry ? { id: entry.id, name: entry.name } : null })
          }
        />
      )}
    </Field>
  )
}

/** Where the result goes: my DM with the agent, a channel I may post in (of the space
 *  when made in one), or a ticket by its key. */
export function PlaceFields({
  values,
  errors,
  onChange,
  types,
  spaceId,
}: {
  values: AutomationValues
  errors: FieldErrors
  onChange: Change
  types: readonly PlaceType[]
  spaceId: string | null
}) {
  const { t } = useTranslation()
  const name = useId()
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-sm font-medium">{t('automations.form.place')}</legend>
      <p className="text-xs text-muted-foreground">{t('automations.form.placeHint')}</p>
      <div className="flex flex-col gap-1.5 sm:flex-row sm:flex-wrap sm:gap-4">
        {types.map((type) => (
          <label key={type} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name={name}
              value={type}
              checked={values.placeType === type}
              onChange={() => onChange({ placeType: type })}
              className="size-4 accent-primary"
            />
            {t(`automations.form.places.${type}`)}
          </label>
        ))}
      </div>
      {values.placeType === 'channel' && (
        <ChannelSelect values={values} error={errors.place} onChange={onChange} spaceId={spaceId} />
      )}
      {values.placeType === 'ticket' && (
        <Field
          label={t('automations.form.ticket')}
          hint={t('automations.form.ticketHint')}
          error={errors.place}
        >
          {(props) => (
            <Input
              {...props}
              inputMode="text"
              autoComplete="off"
              value={values.ticketNumber}
              onChange={(e) => onChange({ ticketNumber: e.target.value })}
            />
          )}
        </Field>
      )}
      {values.placeType === 'dm' && errors.place && (
        <p className="text-xs text-destructive">{errors.place}</p>
      )}
    </fieldset>
  )
}

function ChannelSelect({
  values,
  error,
  onChange,
  spaceId,
}: {
  values: AutomationValues
  error?: string
  onChange: Change
  spaceId: string | null
}) {
  const { t } = useTranslation()
  const channels = useChannels()
  const spaces = useSidebarSpaces()
  const spaceNames = new Map(spaces.items.map((space) => [space.id, space.name]))
  const offered = channels.items.filter(
    (c) =>
      c.kind === 'channel' && !c.archived_at && c.can_post && (!spaceId || c.space_id === spaceId),
  )
  return (
    <Field
      label={t('automations.form.channel')}
      hint={t('automations.form.channelHint')}
      error={error}
    >
      {(props) => (
        <NativeSelect
          {...props}
          value={values.conversationId}
          onChange={(e) => onChange({ conversationId: e.target.value })}
        >
          <option value="">{t('automations.form.channelNone')}</option>
          {offered.map((channel) => (
            <option key={channel.id} value={channel.id}>
              {spaceId
                ? `#${channel.name ?? ''}`
                : t('automations.form.channelOption', {
                    name: channel.name ?? '',
                    space: spaceNames.get(channel.space_id ?? '') ?? '',
                  })}
            </option>
          ))}
        </NativeSelect>
      )}
    </Field>
  )
}
