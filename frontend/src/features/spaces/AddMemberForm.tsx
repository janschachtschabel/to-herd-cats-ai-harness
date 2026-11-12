import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, useWatch } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import { useGroups } from '@/features/admin/groups/queries'
import { useUsers } from '@/features/admin/users/queries'
import { usePermission } from '@/features/auth/queries'
import { Field, SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { bodySchema } from '@/lib/schemas'
import { SPACE_ROLES } from './display'
import { useSetSpaceMember } from './queries'

type Values = Schemas['SpaceMemberIn']
const schema = bodySchema('SpaceMemberIn')

/** Add a person or a group; `present` ("type:id") are left out of the choice. Choosing
 *  needs the lists of the administration. */
export function AddMemberForm({ spaceId, present }: { spaceId: string; present: Set<string> }) {
  const { t } = useTranslation()
  const canListUsers = usePermission('user.manage')
  const canListGroups = usePermission('group.manage')
  const users = useUsers(canListUsers)
  const groups = useGroups(canListGroups)
  const add = useSetSpaceMember(spaceId)
  const types: Values['member_type'][] = []
  if (canListUsers) types.push('user')
  if (canListGroups) types.push('group')
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { member_type: types[0] ?? 'user', member_id: '', role: 'viewer' },
  })
  const memberType = useWatch({ control: form.control, name: 'member_type' })
  const errors = form.formState.errors

  if (types.length === 0) {
    return <p className="text-sm text-muted-foreground">{t('spaces.members.noDirectory')}</p>
  }

  const candidates =
    memberType === 'group'
      ? groups.items
          .filter((g) => !present.has(`group:${g.id}`))
          .map((g) => ({ id: g.id, label: g.name }))
      : users.items
          .filter((u) => u.is_active && !present.has(`user:${u.id}`))
          .map((u) => ({ id: u.id, label: `${u.name} (${u.email})` }))
  const list = memberType === 'group' ? groups : users

  const onSubmit = form.handleSubmit((values) =>
    add.mutate(values, { onSuccess: () => form.reset({ ...values, member_id: '' }) }),
  )

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      aria-labelledby="add-member-heading"
      className="flex flex-col gap-3 rounded-lg border p-4"
    >
      <h3 id="add-member-heading" className="text-sm font-semibold">
        {t('spaces.members.add')}
      </h3>
      <div className="grid gap-3 sm:grid-cols-[10rem_1fr_10rem]">
        <Field label={t('spaces.members.type')}>
          {(props) => (
            <NativeSelect
              {...props}
              {...form.register('member_type', {
                onChange: () => form.setValue('member_id', ''),
              })}
            >
              {types.map((type) => (
                <option key={type} value={type}>
                  {t(`principals.${type}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
        <Field label={t('spaces.members.who')} error={errors.member_id?.message}>
          {(props) => (
            <NativeSelect {...props} disabled={list.isPending} {...form.register('member_id')}>
              <option value="">{t('spaces.members.choose')}</option>
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
        <Field label={t('spaces.members.role')}>
          {(props) => (
            <NativeSelect {...props} {...form.register('role')}>
              {SPACE_ROLES.map((role) => (
                <option key={role} value={role}>
                  {t(`roles.${role}`)}
                </option>
              ))}
            </NativeSelect>
          )}
        </Field>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={add.isPending}>
          {t('spaces.members.addSubmit')}
        </Button>
        {list.hasMore && (
          <Button type="button" variant="ghost" onClick={list.loadMore} disabled={list.loadingMore}>
            {t('spaces.members.moreCandidates')}
          </Button>
        )}
      </div>
      <SaveError error={add.error} />
    </form>
  )
}
