import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import { SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { useSetAgentTools } from '../adminQueries'
import type { AgentTool } from '../levels'
import { choiceOf, choicesFor, entriesWith, reachable, type ExternalAgentChoice } from './choices'

const GRANT_VARIANT = { allow: 'secondary', confirm: 'outline', block: 'destructive' } as const

/** An external agent's grants: only the tools its token can reach over `/mcp` (offered
 *  there, level 2 at most), each allowed or blocked; only "allowed" counts there.
 *  Saves all entries at once with the agent's version (409: reload, choices kept). */
export function ExternalAgentTools({
  shown,
  onReload,
}: {
  shown: Schemas['AgentToolsOut']
  onReload: () => void
}) {
  const { t } = useTranslation()
  const save = useSetAgentTools(shown.agent_id)
  const [draft, setDraft] = useState<Record<string, ExternalAgentChoice>>({})
  const tools = reachable(shown.tools)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate({ tools: entriesWith(shown.tools, draft), version: shown.version })
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg border p-4">
      <h2 className="text-base font-semibold">{t('agents.external.tools.title')}</h2>
      <p className="text-sm text-muted-foreground">{t('agents.external.tools.hint')}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" aria-label={t('agents.external.tools.tableLabel')}>
          <thead className="text-left text-xs text-muted-foreground">
            <tr>
              <th className="py-1 pr-3 font-medium">{t('agents.tools.tool')}</th>
              <th className="py-1 pr-3 font-medium">{t('agents.tools.effective')}</th>
              <th className="py-1 font-medium">{t('agents.external.tools.grant')}</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {tools.map((tool) => (
              <Row
                key={tool.name}
                tool={tool}
                choice={draft[tool.name]}
                onChoose={(choice) => setDraft((d) => ({ ...d, [tool.name]: choice }))}
              />
            ))}
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

function Row({
  tool,
  choice,
  onChoose,
}: {
  tool: AgentTool
  choice: ExternalAgentChoice | undefined
  onChoose: (choice: ExternalAgentChoice) => void
}) {
  const { t } = useTranslation()
  const name = t(`agents.tools.names.${tool.name}`, { defaultValue: tool.name })
  const choices = choicesFor(tool)
  return (
    <tr className="align-top">
      <th scope="row" className="py-2 pr-3 text-left font-normal">
        <span className="font-medium">{name}</span>
        <span className="mt-0.5 flex flex-wrap gap-1">
          <Badge variant="outline">{t(`agents.tools.effects.${tool.effect}`)}</Badge>
          <Badge variant="outline">{t('agents.tools.fromLevel', { level: tool.level })}</Badge>
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
            className="min-w-40"
            value={choice ?? choiceOf(tool.entry)}
            onChange={(e) => onChoose(e.target.value as ExternalAgentChoice)}
          >
            {choices.map((value) => (
              <option key={value} value={value}>
                {t(`agents.external.tools.choices.${value}`)}
              </option>
            ))}
          </NativeSelect>
        )}
      </td>
    </tr>
  )
}
