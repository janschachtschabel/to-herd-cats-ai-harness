import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { NativeSelect } from '@/components/ui/native-select'
import {
  choiceOf,
  entryChoices,
  externalChoiceOf,
  externalChoices,
  type AgentTool,
  type AnyChoice,
} from '../levels'

const GRANT_VARIANT = { allow: 'secondary', confirm: 'outline', block: 'destructive' } as const

interface RowProps {
  tool: AgentTool
  /** The agent's level (an external tool above it is held back until it is raised). */
  level: number
  choice: AnyChoice | undefined
  onChoose: (choice: AnyChoice) => void
}

function Effective({ tool }: { tool: AgentTool }) {
  const { t } = useTranslation()
  return (
    <td className="py-2 pr-3">
      <Badge variant={GRANT_VARIANT[tool.effective]}>
        {t(`agents.tools.grants.${tool.effective}`)}
      </Badge>
    </td>
  )
}

/** A tool of the catalog: its level's default, tightened only. */
export function BuiltInToolRow({ tool, choice, onChoose }: RowProps) {
  const { t } = useTranslation()
  const name = t(`agents.tools.names.${tool.name}`, { defaultValue: tool.name })
  const choices = entryChoices(tool)
  return (
    <tr className="align-top">
      <th scope="row" className="py-2 pr-3 text-left font-normal">
        <span className="font-medium">{name}</span>
        <span className="mt-0.5 flex flex-wrap gap-1">
          <Badge variant="outline">{t(`agents.tools.effects.${tool.effect}`)}</Badge>
          <Badge variant="outline">{t('agents.tools.fromLevel', { level: tool.level })}</Badge>
        </span>
      </th>
      <Effective tool={tool} />
      <td className="py-2">
        {choices.length === 0 ? (
          <span className="text-xs text-muted-foreground">
            {t('agents.tools.unavailable', { level: tool.level })}
          </span>
        ) : (
          <NativeSelect
            aria-label={t('agents.tools.entryFor', { name })}
            className="min-w-44"
            value={choice ?? choiceOf(tool.entry)}
            onChange={(e) => onChoose(e.target.value as AnyChoice)}
          >
            {choices.map((value) => (
              <option key={value} value={value}>
                {t(`agents.tools.choices.${value}`)}
              </option>
            ))}
          </NativeSelect>
        )}
      </td>
    </tr>
  )
}

/** An external server's tool: granted only with an entry; a writing one always waits
 *  for the asking person's release; one that is not usable now (not approved, changed,
 *  or its server off) keeps its entry but is never offered to a run. */
export function ExternalToolRow({ tool, level, choice, onChoose }: RowProps) {
  const { t } = useTranslation()
  const name = tool.external?.tool_name ?? tool.name
  return (
    <tr className="align-top">
      <th scope="row" className="py-2 pr-3 text-left font-normal">
        <span className="font-mono text-sm font-medium break-all">{name}</span>
        <span className="mt-0.5 flex flex-wrap gap-1">
          <Badge variant="outline">{t(`agents.tools.effects.${tool.effect}`)}</Badge>
          <Badge variant="outline">{t('agents.tools.fromLevel', { level: tool.level })}</Badge>
          {tool.external?.usable === false && (
            <Badge variant="destructive">{t('agents.tools.external.unusable')}</Badge>
          )}
        </span>
        {tool.effect === 'write' && (
          <span className="mt-1 block text-xs text-muted-foreground">
            {t('agents.tools.external.alwaysReleased')}
          </span>
        )}
        {level < tool.level && (
          <span className="mt-0.5 block text-xs text-amber-800 dark:text-amber-300">
            {t('agents.tools.external.needsLevel', { level: tool.level })}
          </span>
        )}
      </th>
      <Effective tool={tool} />
      <td className="py-2">
        <NativeSelect
          aria-label={t('agents.tools.entryFor', { name })}
          className="min-w-44"
          value={choice ?? externalChoiceOf(tool.entry)}
          onChange={(e) => onChoose(e.target.value as AnyChoice)}
        >
          {externalChoices(tool).map((value) => (
            <option key={value} value={value}>
              {t(`agents.tools.external.choices.${value}`)}
            </option>
          ))}
        </NativeSelect>
      </td>
    </tr>
  )
}
