import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { SaveError } from '@/features/shared/forms'
import { useSetAgentLevel } from '../adminQueries'
import { LEVELS, offeredLevels } from '../levels'

/** The agent's autonomy level, each in plain words. Only the levels the API lets this
 *  person give are offered (`max_level`); a refusal (`agent.level_denied`) is put
 *  into words by the save error. Saves with the agent's version (409: reload). */
export function AgentLevelForm({
  agentId,
  level,
  maxLevel,
  version,
  onReload,
  withheldNote,
}: {
  agentId: string
  level: number
  maxLevel: number
  version: number
  onReload: () => void
  /** Why higher levels are not offered (default: who may give level 3). */
  withheldNote?: string
}) {
  const { t } = useTranslation()
  const save = useSetAgentLevel(agentId)
  const [chosen, setChosen] = useState(level)
  const offered = offeredLevels(maxLevel, level)
  const withheld = LEVELS.some((l) => !offered.includes(l))

  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate({ level: chosen, version })
  }

  return (
    <form onSubmit={submit}>
      <fieldset className="flex flex-col gap-3 rounded-lg border p-4">
        <legend className="px-1 text-base font-semibold">{t('agents.level.title')}</legend>
        <p className="text-sm text-muted-foreground">{t('agents.level.hint')}</p>
        <div className="flex flex-col gap-2">
          {offered.map((value) => (
            <label key={value} className="flex items-start gap-2 text-sm">
              <input
                type="radio"
                name="agent-level"
                className="mt-1 accent-primary"
                checked={chosen === value}
                onChange={() => setChosen(value)}
              />
              <span>
                <span className="font-medium">{t(`agents.level.names.${value}`)}</span>
                <span className="block text-xs text-muted-foreground">
                  {t(`agents.level.explain.${value}`)}
                </span>
              </span>
            </label>
          ))}
        </div>
        {withheld && (
          <p className="text-xs text-muted-foreground">
            {withheldNote ?? t('agents.level.withheld')}
          </p>
        )}
        <SaveError error={save.error} onReload={onReload} />
        <div>
          <Button type="submit" size="sm" disabled={save.isPending || chosen === level}>
            {t('agents.level.save')}
          </Button>
        </div>
      </fieldset>
    </form>
  )
}
