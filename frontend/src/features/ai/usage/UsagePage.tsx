import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { AiAdminTabs } from '../AiAdminTabs'
import { USAGE_GROUPS, useUsage, type UsageGroup } from '../usageQueries'
import { formatCost, lastThirtyDays } from './period'

/** The organisation's AI usage per UTC day (`ai.manage`), optionally per person, agent,
 *  space or connection. Costs only where a price is stored. */
export function UsagePage() {
  const { t, i18n } = useTranslation()
  const [by, setBy] = useState<UsageGroup>('day')
  const [period, setPeriod] = useState(lastThirtyDays)
  const usage = useUsage(by, period.from, period.to)
  const byId = useId()
  const fromId = useId()
  const toId = useId()
  const number = (n: number) => n.toLocaleString(i18n.language)

  return (
    <div>
      <PageHeader title={t('ai.title')} description={t('ai.usage.description')} />
      <AiAdminTabs />
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={byId}>{t('ai.usage.groupBy')}</Label>
          <NativeSelect
            id={byId}
            value={by}
            onChange={(event) => setBy(event.target.value as UsageGroup)}
          >
            {USAGE_GROUPS.map((group) => (
              <option key={group} value={group}>
                {t(`ai.usage.groups.${group}`)}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={fromId}>{t('ai.usage.from')}</Label>
          <Input
            id={fromId}
            type="date"
            value={period.from}
            max={period.to}
            onChange={(event) =>
              event.target.value && setPeriod({ ...period, from: event.target.value })
            }
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={toId}>{t('ai.usage.to')}</Label>
          <Input
            id={toId}
            type="date"
            value={period.to}
            min={period.from}
            onChange={(event) =>
              event.target.value && setPeriod({ ...period, to: event.target.value })
            }
          />
        </div>
      </div>
      {usage.isPending ? (
        <LoadingState />
      ) : usage.isError ? (
        <ErrorState error={usage.error} onRetry={() => void usage.refetch()} />
      ) : usage.items.length === 0 ? (
        <EmptyState text={t('ai.usage.empty')} />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('ai.usage.day')}</TableHead>
                {by !== 'day' && <TableHead>{t(`ai.usage.groups.${by}`)}</TableHead>}
                <TableHead className="text-right">{t('ai.usage.calls')}</TableHead>
                <TableHead className="text-right">{t('ai.usage.tokensIn')}</TableHead>
                <TableHead className="text-right">{t('ai.usage.tokensOut')}</TableHead>
                <TableHead className="text-right">{t('ai.usage.cost')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {usage.items.map((row) => (
                <TableRow key={`${row.day}-${row.key_id ?? ''}`}>
                  <TableCell>{row.day}</TableCell>
                  {by !== 'day' && <TableCell>{row.name ?? t('ai.usage.unknown')}</TableCell>}
                  <TableCell className="text-right">{number(row.calls)}</TableCell>
                  <TableCell className="text-right">{number(row.tokens_in)}</TableCell>
                  <TableCell className="text-right">{number(row.tokens_out)}</TableCell>
                  <TableCell className="text-right">
                    {formatCost(row.cost, i18n.language) ?? t('ai.usage.noPrice')}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <LoadMore hasMore={usage.hasMore} loading={usage.loadingMore} onLoad={usage.loadMore} />
    </div>
  )
}
