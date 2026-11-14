import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NativeSelect } from '@/components/ui/native-select'
import { useRun } from '@/features/agents/queries'
import { useMe } from '@/features/auth/queries'
import { placeLink, placeText } from '@/features/runs/display'
import { Place } from '@/features/runs/RunHeader'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { ApprovalCardView } from './ApprovalCard'
import { useMyApprovals } from './queries'

/** Where a release was asked: the run's place, linked where the reader may follow it. */
function ApprovalPlace({ runId }: { runId: string }) {
  const { t } = useTranslation()
  const me = useMe()
  const run = useRun(runId)
  if (!run.data) return null
  return (
    <p className="text-xs text-muted-foreground">
      {t('approvals.page.where')}{' '}
      <Place link={placeLink(run.data, me?.user.id)} text={placeText(t, run.data)} />
    </p>
  )
}

/** "Freigaben": the releases agents asked of me, open ones first (or all), each as
 *  its card with where it was asked; it follows decisions and new cards live. */
export function ApprovalsPage() {
  const { t } = useTranslation()
  const [state, setState] = useState<'pending' | 'all'>('pending')
  const list = useMyApprovals(state === 'pending' ? 'pending' : undefined)
  return (
    <div>
      <PageHeader title={t('approvals.page.title')} description={t('approvals.page.description')} />
      <label className="mb-4 flex max-w-48 flex-col gap-1 text-xs text-muted-foreground">
        {t('approvals.page.filter')}
        <NativeSelect
          value={state}
          onChange={(event) => setState(event.target.value === 'all' ? 'all' : 'pending')}
        >
          <option value="pending">{t('approvals.page.pending')}</option>
          <option value="all">{t('approvals.page.all')}</option>
        </NativeSelect>
      </label>
      {list.isPending ? (
        <LoadingState rows={3} />
      ) : list.isError ? (
        <ErrorState error={list.error} onRetry={() => void list.refetch()} />
      ) : list.items.length === 0 ? (
        <EmptyState
          text={state === 'pending' ? t('approvals.page.empty') : t('approvals.page.emptyAll')}
        />
      ) : (
        <>
          <ul aria-label={t('approvals.page.list')} className="flex flex-col gap-4">
            {list.items.map((approval) => (
              <li key={approval.id} className="flex flex-col gap-1">
                <ApprovalPlace runId={approval.run_id} />
                <ApprovalCardView approval={approval} />
              </li>
            ))}
          </ul>
          <LoadMore hasMore={list.hasMore} loading={list.loadingMore} onLoad={list.loadMore} />
        </>
      )}
    </div>
  )
}
