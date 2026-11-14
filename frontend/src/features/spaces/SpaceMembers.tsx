import { Bot, UserRound, UsersRound } from 'lucide-react'
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
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { SaveError } from '@/features/shared/forms'
import type { SpaceMember, SpaceRole } from '@/lib/api'
import { AddMemberForm } from './AddMemberForm'
import { SPACE_ROLES } from './display'
import { useRemoveSpaceMember, useSetSpaceMember, useSpaceMembers } from './queries'

function MemberName({ member }: { member: SpaceMember }) {
  const { t } = useTranslation()
  const Icon =
    member.member_type === 'group' ? UsersRound : member.member_type === 'agent' ? Bot : UserRound
  return (
    <span className="flex items-center gap-2">
      <Icon className="size-4 text-muted-foreground" aria-hidden />
      <span>{member.name}</span>
      <span className="sr-only">({t(`principals.${member.member_type}`)})</span>
    </span>
  )
}

export function SpaceMembers({ spaceId, editable }: { spaceId: string; editable: boolean }) {
  const { t } = useTranslation()
  const members = useSpaceMembers(spaceId)
  const setMember = useSetSpaceMember(spaceId)
  const remove = useRemoveSpaceMember(spaceId)

  if (members.isPending) return <LoadingState rows={2} />
  if (members.isError) {
    return <ErrorState error={members.error} onRetry={() => void members.refetch()} />
  }

  return (
    <div className="flex flex-col gap-4">
      {members.items.length === 0 ? (
        <EmptyState text={t('spaces.members.empty')} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('spaces.members.name')}</TableHead>
              <TableHead className="w-48">{t('spaces.members.role')}</TableHead>
              {editable && (
                <TableHead className="w-0">
                  <span className="sr-only">{t('common.actions')}</span>
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.items.map((member) => (
              <TableRow key={`${member.member_type}:${member.member_id}`}>
                <TableCell>
                  <MemberName member={member} />
                </TableCell>
                <TableCell>
                  {editable ? (
                    <NativeSelect
                      aria-label={t('spaces.members.roleOf', { name: member.name })}
                      value={member.role}
                      disabled={setMember.isPending}
                      onChange={(event) =>
                        setMember.mutate({
                          member_type: member.member_type as 'user' | 'group',
                          member_id: member.member_id,
                          role: event.target.value as SpaceRole,
                        })
                      }
                    >
                      {SPACE_ROLES.map((role) => (
                        <option key={role} value={role}>
                          {t(`roles.${role}`)}
                        </option>
                      ))}
                    </NativeSelect>
                  ) : (
                    t(`roles.${member.role}`)
                  )}
                </TableCell>
                {editable && (
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={remove.isPending}
                      aria-label={t('spaces.members.removeNamed', { name: member.name })}
                      onClick={() => remove.mutate(member)}
                    >
                      {t('actions.remove')}
                    </Button>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <LoadMore hasMore={members.hasMore} loading={members.loadingMore} onLoad={members.loadMore} />
      <SaveError error={setMember.error ?? remove.error} />
      {editable && (
        <AddMemberForm
          spaceId={spaceId}
          present={new Set(members.items.map((m) => `${m.member_type}:${m.member_id}`))}
        />
      )}
    </div>
  )
}
