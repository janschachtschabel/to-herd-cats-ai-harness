import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from '@tanstack/react-router'
import { useMemo } from 'react'
import { Controller, useForm } from 'react-hook-form'
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
import { Field, FormActions } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { bodySchema } from '@/lib/schemas'
import { PageParentSelect } from './PageParentSelect'
import { useCreatePage } from './queries'
import { buildTree, flattenTree } from './tree'
import { useWiki } from './WikiContext'
import { WikiError } from './WikiError'

type Values = Schemas['PageCreate']
const schema = bodySchema('PageCreate')

export function NewPageDialog({
  open,
  initial,
  onOpenChange,
}: {
  open: boolean
  initial: { title?: string; parentId?: string | null }
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('wiki.create.title')}</DialogTitle>
          <DialogDescription>{t('wiki.create.description')}</DialogDescription>
        </DialogHeader>
        {open && <NewPageForm initial={initial} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function NewPageForm({
  initial,
  onDone,
}: {
  initial: { title?: string; parentId?: string | null }
  onDone: () => void
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { space, nodes } = useWiki()
  const create = useCreatePage(space.id)
  const options = useMemo(() => flattenTree(buildTree(nodes)), [nodes])
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { title: initial.title ?? '', parent_id: initial.parentId ?? null },
  })
  const errors = form.formState.errors

  const onSubmit = form.handleSubmit((values) =>
    create.mutate(values, {
      onSuccess: (page) => {
        onDone()
        void navigate({
          to: '/spaces/$spaceId/p/$',
          params: { spaceId: space.id, _splat: page.path },
          search: { view: 'edit' },
        })
      },
    }),
  )

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      className="flex flex-col gap-4"
      aria-label={t('wiki.create.title')}
    >
      <Field label={t('wiki.fields.title')} error={errors.title?.message}>
        {(props) => <Input {...props} autoFocus {...form.register('title')} />}
      </Field>
      <Field label={t('wiki.fields.parent')}>
        {(props) => (
          <Controller
            control={form.control}
            name="parent_id"
            render={({ field }) => (
              <PageParentSelect
                {...props}
                options={options}
                value={field.value ?? null}
                onChange={field.onChange}
              />
            )}
          />
        )}
      </Field>
      <WikiError error={create.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {t('wiki.create.submit')}
        </Button>
      </FormActions>
    </form>
  )
}
