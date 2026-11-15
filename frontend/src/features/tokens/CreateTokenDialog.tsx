import { useForm } from 'react-hook-form'
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
import { bodyResolver } from '@/lib/formResolver'
import { bodySchema } from '@/lib/schemas'
import { MAX_EXPIRY_DAYS } from './display'
import { EMPTY_TOKEN, tokenBody, type TokenValues } from './form'
import { useCreateToken, type CreatedToken } from './queries'
import { ModeFields, ScopeFields, type SpaceChoices } from './TokenFields'

const resolver = bodyResolver<TokenValues>(bodySchema('TokenIn'), tokenBody)

/** Create a token (mine, or an external agent's with `agentId`): name, read or write,
 *  all spaces or chosen ones, days until it expires. The clear text of the answer goes
 *  to `onCreated` and is shown once there. */
export function CreateTokenDialog({
  open,
  agentId,
  spaces,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  agentId?: string
  spaces: SpaceChoices
  onOpenChange: (open: boolean) => void
  onCreated: (token: CreatedToken) => void
}) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('tokens.create.title')}</DialogTitle>
          <DialogDescription>
            {agentId ? t('tokens.create.agentHint') : t('tokens.create.hint')}
          </DialogDescription>
        </DialogHeader>
        {open && (
          <CreateForm
            agentId={agentId}
            spaces={spaces}
            onCancel={() => onOpenChange(false)}
            onCreated={onCreated}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function CreateForm({
  agentId,
  spaces,
  onCancel,
  onCreated,
}: {
  agentId?: string
  spaces: SpaceChoices
  onCancel: () => void
  onCreated: (token: CreatedToken) => void
}) {
  const { t } = useTranslation()
  const create = useCreateToken(agentId)
  const form = useForm<TokenValues>({ resolver, defaultValues: EMPTY_TOKEN })
  const errors = form.formState.errors
  return (
    <form
      noValidate
      className="flex flex-col gap-4"
      onSubmit={form.handleSubmit((values) =>
        create.mutate(tokenBody(values), { onSuccess: onCreated }),
      )}
    >
      <Field
        label={t('tokens.fields.name')}
        hint={t('tokens.fields.nameHint')}
        error={errors.name?.message}
      >
        {(props) => <Input {...props} autoComplete="off" {...form.register('name')} />}
      </Field>
      <ModeFields form={form} forAgent={agentId !== undefined} />
      <ScopeFields form={form} spaces={spaces} forAgent={agentId !== undefined} />
      <Field
        label={t('tokens.fields.days')}
        hint={t('tokens.fields.daysHint', { max: MAX_EXPIRY_DAYS })}
        error={errors.expires_in_days && t('tokens.fields.daysInvalid', { max: MAX_EXPIRY_DAYS })}
      >
        {(props) => (
          <Input
            {...props}
            type="number"
            min={1}
            max={MAX_EXPIRY_DAYS}
            className="w-32"
            {...form.register('expires_in_days', { valueAsNumber: true })}
          />
        )}
      </Field>
      <SaveError error={create.error} />
      <FormActions>
        <Button type="button" variant="outline" onClick={onCancel}>
          {t('actions.cancel')}
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {t('tokens.create.submit')}
        </Button>
      </FormActions>
    </form>
  )
}
