import { Link } from '@tanstack/react-router'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
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
import { GroupDialog } from './GroupDialog'
import { useGroups } from './queries'

export function GroupsPage() {
  const { t } = useTranslation()
  const groups = useGroups()
  const [creating, setCreating] = useState(false)

  return (
    <div>
      <PageHeader
        title={t('groups.title')}
        description={t('groups.description')}
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden />
            {t('groups.create.open')}
          </Button>
        }
      />
      {groups.isPending ? (
        <LoadingState />
      ) : groups.isError ? (
        <ErrorState error={groups.error} onRetry={() => void groups.refetch()} />
      ) : groups.items.length === 0 ? (
        <EmptyState text={t('groups.empty')} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('groups.fields.name')}</TableHead>
              <TableHead>{t('groups.fields.description')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {groups.items.map((group) => (
              <TableRow key={group.id}>
                <TableCell>
                  <Link
                    to="/admin/groups/$groupId"
                    params={{ groupId: group.id }}
                    className="font-medium underline-offset-4 hover:underline"
                  >
                    {group.name}
                  </Link>
                </TableCell>
                <TableCell className="text-muted-foreground">{group.description}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <LoadMore hasMore={groups.hasMore} loading={groups.loadingMore} onLoad={groups.loadMore} />
      <GroupDialog open={creating} onOpenChange={setCreating} />
    </div>
  )
}
