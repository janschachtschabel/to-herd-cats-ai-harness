import { useState } from 'react'
import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { TargetPicker } from '@/features/ai/assignments/TargetPicker'
import type { Connection } from '@/features/ai/display'
import { DirectoryCombobox } from '@/features/directory/DirectoryCombobox'
import { Field } from '@/features/shared/forms'
import type { DirectoryEntry, Schemas } from '@/lib/api'
import { AGENT_STATUSES } from './display'

type Values = Schemas['AgentCreate']
const NONE = new Set<string>()
const MAX_INSTRUCTIONS = 20_000

/** The fields of an agent: who it is, what it is told, which model answers, who is
 *  responsible, its status and its limits. */
export function AgentFields({
  form,
  connections,
  responsible,
}: {
  form: UseFormReturn<Values>
  connections: readonly Connection[]
  /** The responsible person as first shown (a name to display). */
  responsible: DirectoryEntry | null
}) {
  const { t } = useTranslation()
  const errors = form.formState.errors
  const [person, setPerson] = useState<DirectoryEntry | null>(responsible)
  const connectionId = form.watch('connection_id')
  const model = form.watch('model')
  const instructions = form.watch('instructions') ?? ''
  const target = connectionId ? { connection_id: connectionId, model } : null
  const submitted = form.formState.isSubmitted

  return (
    <>
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
        label={t('agents.fields.instructions')}
        hint={t('agents.fields.instructionsHint', {
          count: instructions.length,
          max: MAX_INSTRUCTIONS,
        })}
        error={errors.instructions?.message}
      >
        {(props) => <Textarea {...props} rows={6} {...form.register('instructions')} />}
      </Field>
      <div className="flex flex-col gap-1">
        <TargetPicker
          connections={connections}
          value={target}
          label={t('agents.fields.model')}
          onChange={(next) => {
            form.setValue('connection_id', next?.connection_id ?? '', { shouldValidate: submitted })
            form.setValue('model', next?.model ?? '', { shouldValidate: submitted })
          }}
        />
        {(errors.connection_id || errors.model) && (
          <p className="text-xs text-destructive">{t('agents.fields.modelRequired')}</p>
        )}
      </div>
      <Field
        label={t('agents.fields.responsible')}
        hint={t('agents.fields.responsibleHint')}
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
      <div className="grid gap-4 sm:grid-cols-3">
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
        <Field label={t('agents.fields.maxSteps')} error={errors.max_steps?.message}>
          {(props) => (
            <Input
              {...props}
              type="number"
              min={1}
              max={25}
              {...form.register('max_steps', { valueAsNumber: true })}
            />
          )}
        </Field>
        <Field label={t('agents.fields.maxRuntime')} error={errors.max_runtime_seconds?.message}>
          {(props) => (
            <Input
              {...props}
              type="number"
              min={10}
              max={600}
              {...form.register('max_runtime_seconds', { valueAsNumber: true })}
            />
          )}
        </Field>
      </div>
    </>
  )
}
