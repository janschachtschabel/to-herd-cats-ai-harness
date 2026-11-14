import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import { hasPermission, useMe } from '@/features/auth/queries'
import { DirectoryCombobox } from '@/features/directory/DirectoryCombobox'
import { Field, SaveError } from '@/features/shared/forms'
import { LoadMore } from '@/features/shared/states'
import type { DirectoryEntry } from '@/lib/api'
import { useBudgetAgents, useSetBudget } from '../budgetQueries'
import {
  BUDGET_SCOPES,
  parseLimits,
  type Budget,
  type BudgetScope,
  type BudgetTarget,
  type LimitErrors,
  type LimitInput,
} from './budget'
import { LimitFields } from './LimitFields'

const EMPTY: LimitInput = { tokens: '', cost: '' }

/** Sets a new budget for the organisation, a person or an agent. Who already has one
 *  is not offered again (theirs is changed in the list). Agents can be picked by those
 *  who manage them (`agent.manage`), the only right that lists every agent. */
export function NewBudget({ present }: { present: readonly Budget[] }) {
  const { t } = useTranslation()
  const headingId = useId()
  const me = useMe()
  const managesAgents = hasPermission(me, 'agent.manage')
  const hasOrg = present.some((b) => b.scope === 'organisation')
  const [scope, setScope] = useState<BudgetScope>(hasOrg ? 'user' : 'organisation')
  const [person, setPerson] = useState<DirectoryEntry | null>(null)
  const [agentId, setAgentId] = useState('')
  const [value, setValue] = useState<LimitInput>(EMPTY)
  const [errors, setErrors] = useState<LimitErrors>({})
  const set = useSetBudget()
  const agents = useBudgetAgents(scope === 'agent' && managesAgents)
  const taken = new Set(present.map((b) => `${b.scope}:${b.subject_id ?? ''}`))
  const offeredAgents = agents.items.filter((a) => !taken.has(`agent:${a.id}`))

  const target: BudgetTarget | null =
    scope === 'organisation'
      ? hasOrg
        ? null
        : { scope }
      : scope === 'user'
        ? person && { scope, id: person.id }
        : agentId
          ? { scope, id: agentId }
          : null

  const submit = () => {
    if (!target) return
    const limits = parseLimits(value)
    if (!limits.ok) return setErrors(limits.errors)
    setErrors({})
    const { tokens_per_day, cost_per_day } = limits
    set.mutate(
      { target, body: { tokens_per_day, cost_per_day, version: null } },
      {
        onSuccess: () => {
          setValue(EMPTY)
          setPerson(null)
          setAgentId('')
        },
      },
    )
  }

  return (
    <form
      aria-labelledby={headingId}
      noValidate
      className="flex flex-col gap-3 rounded-lg border p-3"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <h2 id={headingId} className="font-semibold">
        {t('ai.budgets.new')}
      </h2>
      <Field label={t('ai.budgets.scope')}>
        {(props) => (
          <NativeSelect
            {...props}
            value={scope}
            onChange={(event) => {
              setScope(event.target.value as BudgetScope)
              set.reset()
            }}
          >
            {BUDGET_SCOPES.map((option) => (
              <option key={option} value={option} disabled={option === 'organisation' && hasOrg}>
                {t(`ai.budgets.scopeOptions.${option}`)}
              </option>
            ))}
          </NativeSelect>
        )}
      </Field>
      {scope === 'user' && (
        <Field label={t('ai.budgets.person')}>
          {(props) => (
            <DirectoryCombobox
              control={props}
              type="user"
              selected={person}
              exclude={taken}
              onSelect={setPerson}
            />
          )}
        </Field>
      )}
      {scope === 'agent' &&
        (managesAgents ? (
          <>
            <Field label={t('ai.budgets.agent')}>
              {(props) => (
                <NativeSelect
                  {...props}
                  value={agentId}
                  onChange={(event) => setAgentId(event.target.value)}
                >
                  <option value="">{t('ai.budgets.pickAgent')}</option>
                  {offeredAgents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </Field>
            <SaveError error={agents.error} />
            <LoadMore
              hasMore={agents.hasMore}
              loading={agents.loadingMore}
              onLoad={agents.loadMore}
            />
          </>
        ) : (
          <p className="text-sm text-muted-foreground">{t('ai.budgets.agentsNeedRight')}</p>
        ))}
      <LimitFields value={value} onChange={setValue} errors={errors} />
      <div>
        <Button type="submit" size="sm" disabled={!target || set.isPending}>
          {t('ai.budgets.new')}
        </Button>
      </div>
      <SaveError error={set.error} />
    </form>
  )
}
