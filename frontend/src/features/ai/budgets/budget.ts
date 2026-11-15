import type { TFunction } from 'i18next'
import type { Schemas } from '@/lib/api'

export type Budget = Schemas['BudgetOut']
export type BudgetScope = Schemas['BudgetScope']

export const BUDGET_SCOPES: readonly BudgetScope[] = ['organisation', 'user', 'agent']

/** Whose budget a write sets: the organisation's, or a person's or an agent's by id. */
export type BudgetTarget = { scope: 'organisation' } | { scope: 'user' | 'agent'; id: string }

export function targetOf(budget: Budget): BudgetTarget {
  return budget.scope === 'organisation' || !budget.subject_id
    ? { scope: 'organisation' }
    : { scope: budget.scope, id: budget.subject_id }
}

/** Who a budget is for, in words ("Organisation", "Person: Lea Löwe"). */
export function subjectText(t: TFunction, budget: Pick<Budget, 'scope' | 'name'>): string {
  if (budget.scope === 'organisation') return t('ai.budgets.scopes.organisation')
  const name = budget.name ?? t('ai.budgets.gone')
  return t(`ai.budgets.subject.${budget.scope}`, { name })
}

/** The two limits as typed (empty: no such limit). */
export interface LimitInput {
  tokens: string
  cost: string
}

/** Which limit is malformed, or that none was given. */
export type LimitErrors = Partial<Record<'tokens' | 'cost' | 'missing', true>>

/** A budget's limits as the form shows them (the euros with the locale's decimal mark). */
export function limitInput(budget: Budget | undefined, locale: string): LimitInput {
  const cost = budget?.cost_per_day
  return {
    tokens: budget?.tokens_per_day != null ? String(budget.tokens_per_day) : '',
    cost:
      cost != null
        ? new Intl.NumberFormat(locale, { minimumFractionDigits: 2, useGrouping: false }).format(
            Number(cost),
          )
        : '',
  }
}

const MAX_TOKENS = 10 ** 12
const MAX_COST = 1_000_000_000
const TOKENS = /^\d+$/
// Whole euros or with one or two decimals, the mark a comma or a point ("2,50", "2.5").
const COST = /^\d+(?:[.,]\d{1,2})?$/

/** The limits for the API, or what is wrong with them: whole tokens and euros with at
 *  most two decimals, each above zero and within the server's bounds, at least one. */
export function parseLimits(
  input: LimitInput,
):
  | { ok: true; tokens_per_day: number | null; cost_per_day: string | null }
  | { ok: false; errors: LimitErrors } {
  const tokensText = input.tokens.trim()
  const costText = input.cost.trim()
  const errors: LimitErrors = {}
  let tokens: number | null = null
  let cost: string | null = null
  if (tokensText) {
    tokens = TOKENS.test(tokensText) ? Number(tokensText) : NaN
    if (!(tokens > 0 && tokens <= MAX_TOKENS)) errors.tokens = true
  }
  if (costText) {
    cost = costText.replace(',', '.')
    const value = Number(cost)
    if (!COST.test(costText) || !(value > 0 && value <= MAX_COST)) {
      errors.cost = true
    }
  }
  if (!tokensText && !costText) errors.missing = true
  if (Object.keys(errors).length > 0) return { ok: false, errors }
  return { ok: true, tokens_per_day: tokens, cost_per_day: cost }
}

export function formatTokens(tokens: number, locale: string): string {
  return tokens.toLocaleString(locale)
}

export function formatEuro(amount: string | number, locale: string): string {
  return new Intl.NumberFormat(locale, { style: 'currency', currency: 'EUR' }).format(
    Number(amount),
  )
}
