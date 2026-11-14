import { useTranslation } from 'react-i18next'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { AiAdminTabs } from '../AiAdminTabs'
import { useBudgets } from '../budgetQueries'
import { BudgetRow } from './BudgetRow'
import { NewBudget } from './NewBudget'

/** Daily AI budgets (`ai.manage`) per organisation, person or agent, each with today's
 *  use (UTC day). A run that reaches one stops before its next model call. */
export function BudgetsPage() {
  const { t } = useTranslation()
  const budgets = useBudgets()
  return (
    <div>
      <PageHeader title={t('ai.title')} description={t('ai.budgets.description')} />
      <AiAdminTabs />
      <div className="flex max-w-3xl flex-col gap-6">
        <p className="rounded-lg border bg-muted/40 p-3 text-sm">{t('ai.budgets.currencyNote')}</p>
        {budgets.isPending ? (
          <LoadingState rows={2} />
        ) : budgets.isError ? (
          <ErrorState error={budgets.error} onRetry={() => void budgets.refetch()} />
        ) : (
          <>
            {budgets.items.length === 0 ? (
              <EmptyState text={t('ai.budgets.empty')} />
            ) : (
              <ul
                aria-label={t('ai.budgets.listLabel')}
                className="flex flex-col divide-y rounded-lg border"
              >
                {budgets.items.map((budget) => (
                  <BudgetRow key={budget.id} budget={budget} />
                ))}
              </ul>
            )}
            <LoadMore
              hasMore={budgets.hasMore}
              loading={budgets.loadingMore}
              onLoad={budgets.loadMore}
            />
            <NewBudget present={budgets.items} />
          </>
        )}
      </div>
    </div>
  )
}
