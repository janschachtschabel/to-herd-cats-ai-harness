import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import { SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { useSetAgentTools } from '../adminQueries'
import { choiceOf, entryChoices, toolEntries, type AgentTool, type EntryChoice } from '../levels'

const GRANT_VARIANT = { allow: 'secondary', confirm: 'outline', block: 'destructive' } as const

/** Every tool of the catalog with its effective grant: the level's default, tightened
 *  per tool to "only after approval" or "blocked" (never loosened). A tool the level
 *  does not reach is not available. Saves all entries at once with the agent's
 *  version: after a 409 the fresh version is loaded and the choices made are kept. */
export function AgentToolsForm({
  shown,
  onReload,
}: {
  shown: Schemas['AgentToolsOut']
  onReload: () => void
}) {
  const { t } = useTranslation()
  const save = useSetAgentTools(shown.agent_id)
  const [draft, setDraft] = useState<Record<string, EntryChoice>>({})
  const toolName = (tool: AgentTool) =>
    t(`agents.tools.names.${tool.name}`, { defaultValue: tool.name })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate({ tools: toolEntries(shown.tools, draft), version: shown.version })
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg border p-4">
      <h2 className="text-base font-semibold">{t('agents.tools.title')}</h2>
      <p className="text-sm text-muted-foreground">{t('agents.tools.hint')}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" aria-label={t('agents.tools.tableLabel')}>
          <thead className="text-left text-xs text-muted-foreground">
            <tr>
              <th className="py-1 pr-3 font-medium">{t('agents.tools.tool')}</th>
              <th className="py-1 pr-3 font-medium">{t('agents.tools.effective')}</th>
              <th className="py-1 font-medium">{t('agents.tools.entry')}</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {shown.tools.map((tool) => {
              const choices = entryChoices(tool)
              const name = toolName(tool)
              return (
                <tr key={tool.name} className="align-top">
                  <th scope="row" className="py-2 pr-3 text-left font-normal">
                    <span className="font-medium">{name}</span>
                    <span className="mt-0.5 flex flex-wrap gap-1">
                      <Badge variant="outline">{t(`agents.tools.effects.${tool.effect}`)}</Badge>
                      <Badge variant="outline">
                        {t('agents.tools.fromLevel', { level: tool.level })}
                      </Badge>
                    </span>
                  </th>
                  <td className="py-2 pr-3">
                    <Badge variant={GRANT_VARIANT[tool.effective]}>
                      {t(`agents.tools.grants.${tool.effective}`)}
                    </Badge>
                  </td>
                  <td className="py-2">
                    {choices.length === 0 ? (
                      <span className="text-xs text-muted-foreground">
                        {t('agents.tools.unavailable', { level: tool.level })}
                      </span>
                    ) : (
                      <NativeSelect
                        aria-label={t('agents.tools.entryFor', { name })}
                        className="min-w-44"
                        value={draft[tool.name] ?? choiceOf(tool.entry)}
                        onChange={(e) =>
                          setDraft((d) => ({ ...d, [tool.name]: e.target.value as EntryChoice }))
                        }
                      >
                        {choices.map((choice) => (
                          <option key={choice} value={choice}>
                            {t(`agents.tools.choices.${choice}`)}
                          </option>
                        ))}
                      </NativeSelect>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <SaveError error={save.error} onReload={onReload} />
      <div>
        <Button type="submit" size="sm" disabled={save.isPending}>
          {t('agents.tools.save')}
        </Button>
      </div>
    </form>
  )
}
