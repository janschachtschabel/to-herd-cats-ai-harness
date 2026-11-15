import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { useSetAgentTools } from '../adminQueries'
import { splitTools, toolEntries, type AnyChoice } from '../levels'
import { BuiltInToolRow, ExternalToolRow } from './ToolRows'

/** Every tool of the catalog with its effective grant: the level's default, tightened
 *  per tool to "only after approval" or "blocked" (never loosened). A tool the level
 *  does not reach is not available. After the catalog, the external servers' tools,
 *  grouped by server: each granted only with an entry. Saves all entries at once with
 *  the agent's version: after a 409 the fresh version is loaded and the choices made
 *  are kept. */
export function AgentToolsForm({
  shown,
  onReload,
}: {
  shown: Schemas['AgentToolsOut']
  onReload: () => void
}) {
  const { t } = useTranslation()
  const save = useSetAgentTools(shown.agent_id)
  const [draft, setDraft] = useState<Record<string, AnyChoice>>({})
  const { builtIn, servers } = splitTools(shown.tools)
  const row = (tool: Schemas['AgentToolOut']) => ({
    tool,
    level: shown.level,
    choice: draft[tool.name],
    onChoose: (choice: AnyChoice) => setDraft((d) => ({ ...d, [tool.name]: choice })),
  })

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
            {builtIn.map((tool) => (
              <BuiltInToolRow key={tool.name} {...row(tool)} />
            ))}
          </tbody>
          {servers.map((server) => (
            <tbody key={server.id} className="divide-y border-t-2">
              <tr>
                <th
                  scope="colgroup"
                  colSpan={3}
                  className="pt-4 pb-1 text-left text-sm font-semibold"
                >
                  {t('agents.tools.external.group', { server: server.name })}
                  <span className="block text-xs font-normal text-muted-foreground">
                    {t('agents.tools.external.groupHint')}
                  </span>
                </th>
              </tr>
              {server.tools.map((tool) => (
                <ExternalToolRow key={tool.name} {...row(tool)} />
              ))}
            </tbody>
          ))}
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
