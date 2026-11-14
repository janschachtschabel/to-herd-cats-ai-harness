import { Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { FormActions, SaveError } from '@/features/shared/forms'
import { useFreshBudget, useRemoveBudget, useSetBudget } from '../budgetQueries'
import {
  formatEuro,
  formatTokens,
  limitInput,
  parseLimits,
  subjectText,
  targetOf,
  type Budget,
  type LimitErrors,
} from './budget'
import { LimitFields } from './LimitFields'

/** One budget: whom it limits, today's use against each limit, change and remove. */
export function BudgetRow({ budget }: { budget: Budget }) {
  const { t, i18n } = useTranslation()
  const [editing, setEditing] = useState(false)
  const [removing, setRemoving] = useState(false)
  const remove = useRemoveBudget()
  const subject = subjectText(t, budget)
  const locale = i18n.language
  const today = budget.today
  const tokens = formatTokens(today.tokens, locale)
  const cost = formatEuro(today.cost, locale)

  return (
    <li className="flex flex-col gap-2 px-3 py-3 sm:flex-row sm:items-start">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2 font-medium">
          <span className="break-words">{subject}</span>
          {today.exhausted && <Badge variant="destructive">{t('ai.budgets.exhausted')}</Badge>}
        </p>
        <dl className="mt-1 grid gap-x-4 gap-y-0.5 text-sm sm:grid-cols-[auto_1fr]">
          <dt className="text-muted-foreground">{t('ai.budgets.todayTokens')}</dt>
          <dd>
            {budget.tokens_per_day != null
              ? t('ai.budgets.ofLimitTokens', {
                  used: tokens,
                  limit: formatTokens(budget.tokens_per_day, locale),
                })
              : t('ai.budgets.noTokenLimit', { used: tokens })}
          </dd>
          <dt className="text-muted-foreground">{t('ai.budgets.todayCost')}</dt>
          <dd>
            {budget.cost_per_day != null
              ? t('ai.budgets.ofLimit', {
                  used: cost,
                  limit: formatEuro(budget.cost_per_day, locale),
                })
              : t('ai.budgets.noCostLimit', { used: cost })}
          </dd>
          {today.unpriced_calls > 0 && (
            <>
              <dt className="text-muted-foreground">{t('ai.budgets.unpriced')}</dt>
              <dd>{t('ai.budgets.unpricedCalls', { count: today.unpriced_calls })}</dd>
            </>
          )}
        </dl>
      </div>
      <div className="flex gap-1 self-end sm:self-start">
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label={t('ai.budgets.edit', { subject })}
          onClick={() => setEditing(true)}
        >
          <Pencil aria-hidden />
        </Button>
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label={t('ai.budgets.remove', { subject })}
          onClick={() => setRemoving(true)}
        >
          <Trash2 aria-hidden />
        </Button>
      </div>
      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{t('ai.budgets.editTitle', { subject })}</DialogTitle>
          </DialogHeader>
          {editing && <EditBudget budget={budget} onDone={() => setEditing(false)} />}
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={removing}
        title={t('ai.budgets.removeTitle')}
        text={t('ai.budgets.removeText', { subject })}
        confirmLabel={t('actions.remove')}
        destructive
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() =>
          remove.mutate(
            { id: budget.id, version: budget.version },
            { onSuccess: () => setRemoving(false) },
          )
        }
        onOpenChange={(open) => {
          setRemoving(open)
          if (!open) remove.reset()
        }}
      />
    </li>
  )
}

/** Changes the limits against the version it opened with; after a 409 the person
 *  loads the current version and saves again, their input kept as typed. */
function EditBudget({ budget, onDone }: { budget: Budget; onDone: () => void }) {
  const { t, i18n } = useTranslation()
  const set = useSetBudget()
  const fresh = useFreshBudget()
  const [value, setValue] = useState(() => limitInput(budget, i18n.language))
  const [errors, setErrors] = useState<LimitErrors>({})
  const [version, setVersion] = useState<number | null>(budget.version)

  const reload = async () => {
    const current = await fresh(budget.id)
    setVersion(current?.version ?? null)
    set.reset()
  }

  const save = () => {
    const limits = parseLimits(value)
    if (!limits.ok) return setErrors(limits.errors)
    setErrors({})
    const { tokens_per_day, cost_per_day } = limits
    set.mutate(
      { target: targetOf(budget), body: { tokens_per_day, cost_per_day, version } },
      { onSuccess: onDone },
    )
  }

  return (
    <form
      noValidate
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        save()
      }}
    >
      <LimitFields value={value} onChange={setValue} errors={errors} />
      <SaveError error={set.error} onReload={() => void reload()} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={set.isPending}>
          {t('actions.save')}
        </Button>
      </FormActions>
    </form>
  )
}
