import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
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
import { Field, SaveError } from '@/features/shared/forms'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { useAddGroupMember, useGroupMembers, useRemoveGroupMember } from './queries'

export function GroupMembers({ groupId }: { groupId: string }) {
  const { t } = useTranslation()
  const members = useGroupMembers(groupId)
  const users = useUsers()
  const add = useAddGroupMember(groupId)
  const remove = useRemoveGroupMember(groupId)
  const [candidate, setCandidate] = useState('')

  if (members.isPending) return <LoadingState rows={2} />
  if (members.isError) {
    return <ErrorState error={members.error} onRetry={() => void members.refetch()} />
  }

  const present = new Set(members.items.map((m) => m.member_id))
  const candidates = users.items.filter((u) => u.is_active && !present.has(u.id))

  const onAdd = (event: FormEvent) => {
    event.preventDefault()
    if (candidate) add.mutate(candidate, { onSuccess: () => setCandidate('') })
  }

  return (
    <div className="flex flex-col gap-4">
      {members.items.length === 0 ? (
        <EmptyState text={t('groups.members.empty')} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('groups.members.name')}</TableHead>
              <TableHead className="w-0">
                <span className="sr-only">{t('common.actions')}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.items.map((member) => (
              <TableRow key={member.member_id}>
                <TableCell>{member.name}</TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={remove.isPending}
                    aria-label={t('groups.members.removeNamed', { name: member.name })}
                    onClick={() => remove.mutate(member.member_id)}
                  >
                    {t('actions.remove')}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <LoadMore hasMore={members.hasMore} loading={members.loadingMore} onLoad={members.loadMore} />
      <form onSubmit={onAdd} className="flex flex-wrap items-end gap-2 rounded-lg border p-4">
        <div className="min-w-64 flex-1">
          <Field label={t('groups.members.add')}>
            {(props) => (
              <NativeSelect
                {...props}
                value={candidate}
                disabled={users.isPending}
                onChange={(event) => setCandidate(event.target.value)}
              >
                <option value="">{t('groups.members.choose')}</option>
                {candidates.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.name} ({user.email})
                  </option>
                ))}
              </NativeSelect>
            )}
          </Field>
        </div>
        <Button type="submit" disabled={!candidate || add.isPending}>
          {t('groups.members.addSubmit')}
        </Button>
        {users.hasMore && (
          <Button type="button" variant="ghost" onClick={users.loadMore}>
            {t('groups.members.morePeople')}
          </Button>
        )}
      </form>
      <SaveError error={add.error ?? remove.error} />
    </div>
  )
}
