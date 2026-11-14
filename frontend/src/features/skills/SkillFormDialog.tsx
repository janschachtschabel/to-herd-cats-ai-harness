import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useState, type ReactNode } from 'react'
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
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { bodySchema } from '@/lib/schemas'
import { MarkdownField } from './MarkdownField'
import { skillQuery, useCreateSkill, useUpdateSkill, type SkillDetail } from './queries'

type Values = Schemas['SkillCreate']
const schema = bodySchema('SkillCreate')

/** Create a skill (`skill` absent: in `spaceId`, or organisation-wide with null), or
 *  change one with its version (409: reload, input kept). `where` is an optional
 *  control above the fields (the administration's choice of the space). */
export function SkillFormDialog({
  open,
  skill,
  spaceId = null,
  where,
  onOpenChange,
}: {
  open: boolean
  skill?: SkillDetail
  spaceId?: string | null
  where?: ReactNode
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {skill ? t('skills.edit.title', { name: skill.name }) : t('skills.create.title')}
          </DialogTitle>
          <DialogDescription>{t('skills.form.hint')}</DialogDescription>
        </DialogHeader>
        {open && (
          <SkillForm
            skill={skill}
            spaceId={spaceId}
            where={where}
            onDone={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function SkillForm({
  skill,
  spaceId,
  where,
  onDone,
}: {
  skill?: SkillDetail
  spaceId: string | null
  where?: ReactNode
  onDone: () => void
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const create = useCreateSkill()
  const update = useUpdateSkill(skill?.id ?? '')
  const save = skill ? update : create
  const [version, setVersion] = useState(skill?.version ?? 0)
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: skill?.name ?? '',
      description: skill?.description ?? '',
      content: skill?.content ?? '',
    },
  })
  const errors = form.formState.errors
  const content = useWatch({ control: form.control, name: 'content' })

  const reload = async () => {
    if (!skill) return
    const fresh = await queryClient.fetchQuery({ ...skillQuery(skill.id), staleTime: 0 })
    setVersion(fresh.version)
    update.reset()
  }

  const onSubmit = form.handleSubmit((values) => {
    if (skill) {
      update.mutate({ ...values, version }, { onSuccess: onDone })
      return
    }
    create.mutate(
      { ...values, space_id: spaceId },
      {
        onSuccess: (created) => {
          onDone()
          void navigate({ to: '/skills/$skillId', params: { skillId: created.id } })
        },
      },
    )
  })

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      {where}
      <Field
        label={t('skills.fields.name')}
        hint={t('skills.fields.nameHint')}
        error={errors.name?.message}
      >
        {(props) => <Input {...props} autoComplete="off" {...form.register('name')} />}
      </Field>
      <Field
        label={t('skills.fields.description')}
        hint={t('skills.fields.descriptionHint')}
        error={errors.description?.message}
      >
        {(props) => <Input {...props} {...form.register('description')} />}
      </Field>
      <MarkdownField
        label={t('skills.fields.content')}
        value={content}
        error={errors.content?.message}
        textarea={form.register('content')}
      />
      <SaveError error={save.error} onReload={skill ? () => void reload() : undefined} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={save.isPending}>
          {skill ? t('actions.save') : t('skills.create.submit')}
        </Button>
      </FormActions>
    </form>
  )
}
