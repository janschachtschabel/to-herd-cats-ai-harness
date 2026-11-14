import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { useSetPersonalAgents } from '../assignmentQueries'

/** Whether people with AI may make personal agents. Off, nobody makes new ones and the
 *  existing ones stop answering (they are kept). Saves at the overview's version. */
export function PersonalAgentsSwitch({
  overview,
  onReload,
}: {
  overview: Schemas['AssignmentsOut']
  onReload: () => void
}) {
  const { t } = useTranslation()
  const save = useSetPersonalAgents()
  const id = useId()
  return (
    <section aria-labelledby={`${id}-heading`} className="flex flex-col gap-3">
      <div>
        <h2 id={`${id}-heading`} className="font-semibold">
          {t('ai.assignments.personal.title')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('ai.assignments.personal.hint')}</p>
      </div>
      <label htmlFor={id} className="flex items-center gap-2 text-sm">
        <input
          id={id}
          type="checkbox"
          className="size-4 accent-primary"
          checked={overview.personal_agents}
          disabled={save.isPending}
          onChange={(event) =>
            save.mutate({ enabled: event.target.checked, version: overview.version })
          }
        />
        {t('ai.assignments.personal.label')}
      </label>
      <p role="status" className="text-xs text-muted-foreground">
        {overview.personal_agents
          ? t('ai.assignments.personal.on')
          : t('ai.assignments.personal.off')}
      </p>
      <SaveError
        error={save.error}
        onReload={() => {
          save.reset()
          onReload()
        }}
      />
    </section>
  )
}
