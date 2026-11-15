import { useState } from 'react'
import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { DirectoryCombobox } from '@/features/directory/DirectoryCombobox'
import { Field } from '@/features/shared/forms'
import type { DirectoryEntry } from '@/lib/api'
import { AGENT_STATUSES } from '../display'
import { EXTERNAL_LEVELS, type ExternalValues } from './form'

const NONE = new Set<string>()

/** The fields of an external agent: who it is, who answers for it, its status, and (when
 *  creating) its level, 1 or 2. No model, no instructions: it runs elsewhere. */
export function ExternalAgentFields({
  form,
  responsible,
  withLevel,
}: {
  form: UseFormReturn<ExternalValues>
  responsible: DirectoryEntry | null
  withLevel: boolean
}) {
  const { t } = useTranslation()
  const errors = form.formState.errors
  const submitted = form.formState.isSubmitted
  const [person, setPerson] = useState<DirectoryEntry | null>(responsible)
  return (
    <>
      <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
        {t('agents.external.explain')}
      </p>
      <Field label={t('agents.fields.name')} error={errors.name?.message}>
        {(props) => <Input {...props} {...form.register('name')} />}
      </Field>
      <Field
        label={t('agents.fields.intro')}
        hint={t('agents.fields.introHint')}
        error={errors.intro?.message}
      >
        {(props) => <Textarea {...props} rows={2} {...form.register('intro')} />}
      </Field>
      <Field
        label={t('agents.fields.responsible')}
        hint={t('agents.external.responsibleHint')}
        error={errors.responsible_user_id && t('agents.fields.responsibleRequired')}
      >
        {(props) => (
          <DirectoryCombobox
            control={props}
            type="user"
            selected={person}
            exclude={NONE}
            onSelect={(entry) => {
              setPerson(entry)
              form.setValue('responsible_user_id', entry?.id ?? '', { shouldValidate: submitted })
            }}
          />
        )}
      </Field>
      {withLevel && (
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium">{t('agents.level.title')}</legend>
          {EXTERNAL_LEVELS.map((level) => (
            <label key={level} className="flex items-start gap-2 text-sm">
              <input
                type="radio"
                value={String(level)}
                className="mt-1 accent-primary"
                {...form.register('level')}
              />
              <span>
                <span className="font-medium">{t(`agents.level.names.${level}`)}</span>
                <span className="block text-xs text-muted-foreground">
                  {t(`agents.external.levels.${level}`)}
                </span>
              </span>
            </label>
          ))}
        </fieldset>
      )}
      <Field label={t('agents.fields.status')} hint={t('agents.fields.statusHint')}>
        {(props) => (
          <NativeSelect {...props} {...form.register('status')}>
            {AGENT_STATUSES.map((status) => (
              <option key={status} value={status}>
                {t(`agents.status.${status}`)}
              </option>
            ))}
          </NativeSelect>
        )}
      </Field>
    </>
  )
}
