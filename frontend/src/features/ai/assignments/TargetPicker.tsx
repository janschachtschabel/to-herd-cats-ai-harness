import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { chatConnections, type Connection } from '../display'

export interface Target {
  connection_id: string
  model: string
}

/** A connection and one of its models, or nothing (`noneLabel`, when given). Disabled
 *  connections stay listed, marked, so a stored choice is never silently dropped. */
export function TargetPicker({
  connections,
  value,
  onChange,
  noneLabel,
  label,
}: {
  connections: readonly Connection[]
  value: Target | null
  onChange: (target: Target | null) => void
  noneLabel?: string
  label: string
}) {
  const { t } = useTranslation()
  const connectionId = useId()
  const modelId = useId()
  const offered = chatConnections(connections)
  const current = offered.find((c) => c.id === value?.connection_id)

  const pickConnection = (id: string) => {
    const connection = offered.find((c) => c.id === id)
    onChange(connection ? { connection_id: id, model: connection.models[0] ?? '' } : null)
  }

  return (
    <fieldset className="grid gap-3 sm:grid-cols-2">
      <legend className="sr-only">{label}</legend>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={connectionId}>{t('ai.assignments.connection')}</Label>
        <NativeSelect
          id={connectionId}
          value={value?.connection_id ?? ''}
          onChange={(event) => pickConnection(event.target.value)}
        >
          {(noneLabel !== undefined || !value) && <option value="">{noneLabel ?? ''}</option>}
          {offered.map((connection) => (
            <option key={connection.id} value={connection.id}>
              {connection.enabled
                ? connection.name
                : t('ai.assignments.disabledConnection', { name: connection.name })}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={modelId}>{t('ai.assignments.model')}</Label>
        <NativeSelect
          id={modelId}
          value={value?.model ?? ''}
          disabled={!current}
          onChange={(event) =>
            value && onChange({ connection_id: value.connection_id, model: event.target.value })
          }
        >
          {!current && <option value="" />}
          {current?.models.map((model) => (
            <option key={model} value={model}>
              {model}
            </option>
          ))}
        </NativeSelect>
      </div>
    </fieldset>
  )
}
