import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate, useParams } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import * as z from 'zod'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import type { Space } from '@/lib/api'
import { blankToNull, bodySchema } from '@/lib/schemas'
import { useCreateChannel } from './queries'

const schema = bodySchema('ChannelCreate').and(z.object({ spaceId: z.string().min(1) }))
type Values = z.infer<typeof schema>

/** Creates a channel in one of `spaces` (those where one may manage channels). */
export function CreateChannelDialog({
  spaces,
  open,
  onOpenChange,
}: {
  spaces: Space[]
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('messaging.channel.createTitle')}</DialogTitle>
          <DialogDescription>{t('messaging.channel.createDescription')}</DialogDescription>
        </DialogHeader>
        {open && <CreateChannelForm spaces={spaces} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function CreateChannelForm({ spaces, onDone }: { spaces: Space[]; onDone: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const here = useParams({ strict: false, select: (p) => p.spaceId ?? null })
  const create = useCreateChannel()
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      spaceId: spaces.find((s) => s.id === here)?.id ?? spaces[0]?.id ?? '',
      name: '',
      topic: null,
    },
  })
  const errors = form.formState.errors

  const onSubmit = form.handleSubmit((values) =>
    create.mutate(values, {
      onSuccess: (channel) => {
        onDone()
        void navigate({ to: '/c/$conversationId', params: { conversationId: channel.id } })
      },
    }),
  )

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <Field label={t('messaging.channel.space')} error={errors.spaceId?.message}>
        {(props) => (
          <NativeSelect {...props} {...form.register('spaceId')}>
            {spaces.map((space) => (
              <option key={space.id} value={space.id}>
                {space.name}
              </option>
            ))}
          </NativeSelect>
        )}
      </Field>
      <Field label={t('messaging.channel.name')} error={errors.name?.message}>
        {(props) => <Input {...props} autoFocus {...form.register('name')} />}
      </Field>
      <Field
        label={t('messaging.channel.topic')}
        hint={t('messaging.channel.topicHint')}
        error={errors.topic?.message}
      >
        {(props) => <Input {...props} {...form.register('topic', { setValueAs: blankToNull })} />}
      </Field>
      <SaveError error={create.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onDone}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {t('messaging.channel.createSubmit')}
        </Button>
      </FormActions>
    </form>
  )
}
