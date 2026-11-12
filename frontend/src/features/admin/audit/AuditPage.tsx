import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NativeSelect } from '@/components/ui/native-select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useUsers } from '@/features/admin/users/queries'
import { usePermission } from '@/features/auth/queries'
import { Field } from '@/features/shared/forms'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { formatDateTime } from '@/lib/format'
import { AUDIT_ACTIONS, summarizeDetails, type DetailWords } from './describe'
import { useAudit, type AuditFilter } from './queries'

// Details whose values are enum members with their own translations.
const DETAIL_VALUE_KEYS: Record<string, string> = {
  role: 'roles',
  system_role: 'systemRoles',
  member_type: 'principals',
  kind: 'audit.kinds',
  locale: 'userMenu.locales',
}

export function AuditPage() {
  const { t, i18n } = useTranslation()
  const [filter, setFilter] = useState<AuditFilter>({})
  const entries = useAudit(filter)
  const people = useUsers(usePermission('user.manage'))
  const words: DetailWords = {
    key: (key) => t(`audit.detailKeys.${key}`, { defaultValue: key }),
    value: (key, value) => {
      const prefix = DETAIL_VALUE_KEYS[key]
      return prefix ? t(`${prefix}.${value}`, { defaultValue: value }) : value
    },
  }

  return (
    <div>
      <PageHeader title={t('audit.title')} description={t('audit.description')} />
      <div className="mb-6 grid gap-3 sm:grid-cols-2">
        <Field label={t('audit.filter.actor')}>
          {(props) => (
            <NativeSelect
              {...props}
              value={filter.actorId ?? ''}
              onChange={(e) => setFilter({ ...filter, actorId: e.target.value || undefined })}
            >
              <option value="">{t('audit.filter.anyone')}</option>
              {people.items.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.name}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
        <Field label={t('audit.filter.action')}>
          {(props) => (
            <NativeSelect
              {...props}
              value={filter.action ?? ''}
              onChange={(e) => setFilter({ ...filter, action: e.target.value || undefined })}
            >
              <option value="">{t('audit.filter.anything')}</option>
              {AUDIT_ACTIONS.map((action) => (
                <option key={action} value={action}>
                  {t(`audit.actions.${action}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
      </div>
      {entries.isPending ? (
        <LoadingState />
      ) : entries.isError ? (
        <ErrorState error={entries.error} onRetry={() => void entries.refetch()} />
      ) : entries.items.length === 0 ? (
        <EmptyState text={t('audit.empty')} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('audit.fields.when')}</TableHead>
              <TableHead>{t('audit.fields.actor')}</TableHead>
              <TableHead>{t('audit.fields.action')}</TableHead>
              <TableHead>{t('audit.fields.target')}</TableHead>
              <TableHead>{t('audit.fields.details')}</TableHead>
              <TableHead>{t('audit.fields.ip')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.items.map((entry) => (
              <TableRow key={entry.id}>
                <TableCell className="whitespace-nowrap text-muted-foreground">
                  {formatDateTime(entry.created_at, i18n.language)}
                </TableCell>
                <TableCell>{entry.actor_name ?? t(`principals.${entry.actor_type}`)}</TableCell>
                <TableCell>
                  {t(`audit.actions.${entry.action}`, { defaultValue: entry.action })}
                </TableCell>
                <TableCell>
                  {t(`audit.targets.${entry.target_type}`, { defaultValue: entry.target_type })}
                </TableCell>
                <TableCell className="max-w-80 text-xs break-words whitespace-normal text-muted-foreground">
                  {summarizeDetails(entry.details, words)}
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {entry.ip ?? '–'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <LoadMore hasMore={entries.hasMore} loading={entries.loadingMore} onLoad={entries.loadMore} />
    </div>
  )
}
