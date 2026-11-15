import { useTranslation } from 'react-i18next'
import type { Sprint } from '@/lib/api'

/** A sprint as an option of a select: its name, marked while it runs or once closed. */
export function SprintOption({ sprint, disabled }: { sprint: Sprint; disabled?: boolean }) {
  const { t } = useTranslation()
  return (
    <option value={sprint.id} disabled={disabled}>
      {sprint.state === 'planned'
        ? sprint.name
        : t(`tickets.sprints.option.${sprint.state}`, { name: sprint.name })}
    </option>
  )
}
