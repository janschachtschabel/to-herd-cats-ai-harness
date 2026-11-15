import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { Field, FormActions, SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { bodySchema } from '@/lib/schemas'
import { AGENT_STATUSES } from '../display'
import { agentQuery, useCreateAgent, useUpdateAgent, type Agent } from '../queries'

type Values = Schemas['AgentCreate']
const schema = bodySchema('AgentCreate')

/** What a personal agent's form sends: the rest the API takes from its owner. */
function fieldsOf(values: Values) {
  const { name, intro, instructions, status } = values
  return { name, intro, instructions, status }
}

/** Who the agent is and what it is told; its status. A personal agent takes its
 *  owner's model and has its owner as responsible person (the API sets both). */
function Fields({ form }: { form: ReturnType<typeof useForm<Values>> }) {
  const { t } = useTranslation()
  const errors = form.formState.errors
  return (
    <>
      <Field label={t('agents.fields.name')} error={errors.name?.message}>
        {(props) => <Input {...props} {...form.register('name')} />}
      </Field>
      <Field
        label={t('agents.fields.intro')}
        hint={t('agents.fields.introHint')}
        error={errors.intro?.message}
      >
        {(props) => <Textarea {...props} rows={2} {...form.register('intro')} />}
      </Field>
      <Field
        label={t('agents.fields.instructions')}
        hint={t('agents.personal.instructionsHint')}
        error={errors.instructions?.message}
      >
        {(props) => <Textarea {...props} rows={6} {...form.register('instructions')} />}
      </Field>
      <Field label={t('agents.fields.status')} hint={t('agents.fields.statusHint')}>
        {(props) => (
          <NativeSelect {...props} {...form.register('status')}>
            {AGENT_STATUSES.map((status) => (
              <option key={status} value={status}>
                {t(`agents.status.${status}`)}
              </option>
            ))}
          </NativeSelect>
        )}
      </Field>
    </>
  )
}

function Actions({
  pending,
  submit,
  onDone,
}: {
  pending: boolean
  submit: string
  onDone: () => void
}) {
  const { t } = useTranslation()
  return (
    <FormActions>
      <Button type="button" variant="outline" onClick={onDone}>
        {t('actions.cancel')}
      </Button>
      <Button type="submit" disabled={pending}>
        {submit}
      </Button>
    </FormActions>
  )
}

function CreateForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const create = useCreateAgent()
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', intro: '', instructions: '', status: 'active' },
  })
  return (
    <form
      noValidate
      className="flex flex-col gap-4"
      onSubmit={form.handleSubmit((values) =>
        create.mutate({ ...fieldsOf(values), personal: true }, { onSuccess: onDone }),
      )}
    >
      <p className="text-sm text-muted-foreground">{t('agents.personal.createHint')}</p>
      <Fields form={form} />
      <SaveError error={create.error} />
      <Actions pending={create.isPending} submit={t('agents.create.submit')} onDone={onDone} />
    </form>
  )
}

function EditForm({ agent, onDone }: { agent: Agent; onDone: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const update = useUpdateAgent(agent.id)
  const [version, setVersion] = useState(agent.version)
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: agent.name,
      intro: agent.intro,
      instructions: agent.instructions,
      status: agent.status,
    },
  })
  const reload = async () => {
    const fresh = await queryClient.fetchQuery({ ...agentQuery(agent.id), staleTime: 0 })
    setVersion(fresh.version)
    update.reset()
  }
  return (
    <form
      noValidate
      className="flex flex-col gap-4"
      onSubmit={form.handleSubmit((values) =>
        update.mutate({ ...fieldsOf(values), version }, { onSuccess: onDone }),
      )}
    >
      <Fields form={form} />
      <SaveError error={update.error} onReload={() => void reload()} />
      <Actions pending={update.isPending} submit={t('actions.save')} onDone={onDone} />
    </form>
  )
}

/** Make a personal agent (no `agent`) or change one (with its version; 409 on a
 *  stale one). Refusals (switched off, the limit reached) are put into words. */
export function PersonalAgentDialog({
  open,
  agent,
  onOpenChange,
}: {
  open: boolean
  agent?: Agent
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const done = () => onOpenChange(false)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {agent
              ? t('agents.edit.title', { name: agent.name })
              : t('agents.personal.createTitle')}
          </DialogTitle>
        </DialogHeader>
        {open && (agent ? <EditForm agent={agent} onDone={done} /> : <CreateForm onDone={done} />)}
      </DialogContent>
    </Dialog>
  )
}
