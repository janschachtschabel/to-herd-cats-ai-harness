import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import type { Schemas, Tag } from '@/lib/api'
import { bodySchema } from '@/lib/schemas'
import { freshTag, type TagScope, useCreateTag, useUpdateTag } from './queries'

/** The colour a new tag starts with (the server's default too). */
const DEFAULT_TAG_COLOR = '#64748b'

const createSchema = bodySchema('TagCreate')

// Name and colour carry the same limits in create and update; `space_id` is never a
// form field (the scope decides it).
type TagValues = Schemas['TagCreate']

/** Create a tag in `scope` (no `tag`) or change one: name and colour. */
export function TagDialog({
  open,
  scope,
  tag,
  onOpenChange,
}: {
  open: boolean
  scope: TagScope
  tag?: Tag
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const done = () => onOpenChange(false)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{tag ? t('tags.edit.title') : t('tags.create.title')}</DialogTitle>
        </DialogHeader>
        {open &&
          (tag ? (
            <EditTagForm scope={scope} tag={tag} onDone={done} />
          ) : (
            <CreateTagForm scope={scope} onDone={done} />
          ))}
      </DialogContent>
    </Dialog>
  )
}

const lower = (color: string | undefined) => (color ?? DEFAULT_TAG_COLOR).toLowerCase()

function useTagForm(defaults: TagValues) {
  return useForm<TagValues>({ resolver: zodResolver(createSchema), defaultValues: defaults })
}

function CreateTagForm({ scope, onDone }: { scope: TagScope; onDone: () => void }) {
  const { t } = useTranslation()
  const create = useCreateTag(scope)
  const form = useTagForm({ name: '', color: DEFAULT_TAG_COLOR })
  return (
    <form
      onSubmit={form.handleSubmit((values) =>
        create.mutate({ name: values.name, color: lower(values.color) }, { onSuccess: onDone }),
      )}
      noValidate
      className="flex flex-col gap-4"
    >
      <TagFields form={form} />
      <SaveError error={create.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {t('tags.create.submit')}
        </Button>
      </FormActions>
    </form>
  )
}

function EditTagForm({ scope, tag, onDone }: { scope: TagScope; tag: Tag; onDone: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const update = useUpdateTag(tag.id)
  const [version, setVersion] = useState(tag.version)
  const form = useTagForm({ name: tag.name, color: tag.color })

  // After a conflict: the current version, keeping what was typed.
  const reload = async () => {
    const fresh = await freshTag(queryClient, scope, tag.id)
    if (fresh) setVersion(fresh.version)
    update.reset()
  }

  return (
    <form
      onSubmit={form.handleSubmit((values) =>
        update.mutate(
          { name: values.name, color: lower(values.color), version },
          { onSuccess: onDone },
        ),
      )}
      noValidate
      className="flex flex-col gap-4"
    >
      <TagFields form={form} />
      <SaveError error={update.error} onReload={() => void reload()} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={update.isPending}>
          {t('actions.save')}
        </Button>
      </FormActions>
    </form>
  )
}

/** Name, and the colour as `#rrggbb` text with a picker beside it. */
function TagFields({ form }: { form: UseFormReturn<TagValues> }) {
  const { t } = useTranslation()
  const errors = form.formState.errors
  const color = form.watch('color') ?? ''
  const valid = /^#[0-9a-fA-F]{6}$/.test(color)
  return (
    <>
      <Field label={t('tags.fields.name')} error={errors.name?.message}>
        {(props) => <Input {...props} autoFocus maxLength={50} {...form.register('name')} />}
      </Field>
      <Field
        label={t('tags.fields.color')}
        hint={t('tags.fields.colorHint')}
        error={errors.color?.message}
      >
        {(props) => (
          <div className="flex items-center gap-2">
            <input
              type="color"
              aria-label={t('tags.fields.colorPicker')}
              className="h-8 w-10 shrink-0 cursor-pointer rounded-md border bg-transparent p-0.5"
              value={valid ? color.toLowerCase() : DEFAULT_TAG_COLOR}
              onChange={(e) => form.setValue('color', e.target.value, { shouldValidate: true })}
            />
            <Input {...props} className="font-mono" {...form.register('color')} />
          </div>
        )}
      </Field>
    </>
  )
}
