import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from '@tanstack/react-router'
import { useForm, useWatch } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { blankToNull, bodySchema } from '@/lib/schemas'
import { cn } from '@/lib/utils'
import { useCreateSpace } from './queries'

type Values = Schemas['SpaceCreate']
const schema = bodySchema('SpaceCreate')
const CREATABLE = ['open', 'team'] as const

export function CreateSpaceDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('spaces.create.title')}</DialogTitle>
          <DialogDescription>{t('spaces.create.description')}</DialogDescription>
        </DialogHeader>
        {open && <CreateSpaceForm onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function CreateSpaceForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const create = useCreateSpace()
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { kind: 'team', name: '', description: null, icon: null },
  })
  const kind = useWatch({ control: form.control, name: 'kind' })
  const errors = form.formState.errors

  const onSubmit = form.handleSubmit((values) =>
    create.mutate(values, {
      onSuccess: (space) => {
        onDone()
        void navigate({ to: '/spaces/$spaceId', params: { spaceId: space.id } })
      },
    }),
  )

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1.5 text-sm font-medium">{t('spaces.fields.kind')}</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {CREATABLE.map((value) => (
            <label
              key={value}
              className={cn(
                'flex cursor-pointer flex-col gap-1 rounded-lg border p-3 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring',
                kind === value && 'border-primary bg-accent',
              )}
            >
              <span className="flex items-center gap-2 font-medium">
                <input
                  type="radio"
                  value={value}
                  {...form.register('kind')}
                  className="accent-primary"
                />
                {t(`spaces.kinds.${value}.label`)}
              </span>
              <span className="text-muted-foreground">{t(`spaces.kinds.${value}.hint`)}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid grid-cols-[1fr_6rem] gap-3">
        <Field label={t('spaces.fields.name')} error={errors.name?.message}>
          {(props) => <Input {...props} autoFocus {...form.register('name')} />}
        </Field>
        <Field label={t('spaces.fields.icon')} error={errors.icon?.message}>
          {(props) => <Input {...props} {...form.register('icon', { setValueAs: blankToNull })} />}
        </Field>
      </div>
      <Field label={t('spaces.fields.description')} error={errors.description?.message}>
        {(props) => (
          <Textarea
            {...props}
            rows={3}
            {...form.register('description', { setValueAs: blankToNull })}
          />
        )}
      </Field>
      <SaveError error={create.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {t('spaces.create.submit')}
        </Button>
      </FormActions>
    </form>
  )
}
