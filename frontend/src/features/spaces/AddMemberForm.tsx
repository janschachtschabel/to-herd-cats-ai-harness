import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import { usePermission } from '@/features/auth/queries'
import { DirectoryCombobox } from '@/features/directory/DirectoryCombobox'
import { Field, SaveError } from '@/features/shared/forms'
import type { DirectoryEntry, Schemas } from '@/lib/api'
import { bodySchema } from '@/lib/schemas'
import { SPACE_ROLES } from './display'
import { useSetSpaceMember } from './queries'

type Values = Schemas['SpaceMemberIn']
const schema = bodySchema('SpaceMemberIn')

/** Add a person or a group, found in the directory; `present` ("type:id") are not
 *  offered again. Searching needs `directory.read` (everyone but guests). */
export function AddMemberForm({ spaceId, present }: { spaceId: string; present: Set<string> }) {
  const { t } = useTranslation()
  const canSearch = usePermission('directory.read')
  const add = useSetSpaceMember(spaceId)
  const [picked, setPicked] = useState<DirectoryEntry | null>(null)
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { member_type: 'user', member_id: '', role: 'viewer' },
  })
  const errors = form.formState.errors

  if (!canSearch) {
    return <p className="text-sm text-muted-foreground">{t('spaces.members.noDirectory')}</p>
  }

  const choose = (entry: DirectoryEntry | null) => {
    setPicked(entry)
    form.setValue('member_type', entry?.type ?? 'user')
    form.setValue('member_id', entry?.id ?? '', { shouldValidate: form.formState.isSubmitted })
  }

  const onSubmit = form.handleSubmit((values) =>
    add.mutate(values, {
      onSuccess: () => {
        setPicked(null)
        form.reset({ ...values, member_id: '' })
      },
    }),
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
      <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
        <Field
          label={t('spaces.members.who')}
          hint={t('directory.hint')}
          error={errors.member_id && t('spaces.members.pickRequired')}
        >
          {(props) => (
            <DirectoryCombobox
              control={props}
              selected={picked}
              onSelect={choose}
              exclude={present}
            />
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
      <div>
        <Button type="submit" disabled={add.isPending}>
          {t('spaces.members.addSubmit')}
        </Button>
      </div>
      <SaveError error={add.error} />
    </form>
  )
}
