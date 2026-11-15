import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useMe } from '@/features/auth/queries'
import { FormActions, SaveError } from '@/features/shared/forms'
import type { DirectoryEntry } from '@/lib/api'
import { bodyResolver } from '@/lib/formResolver'
import { bodySchema } from '@/lib/schemas'
import { agentQuery, useCreateAgent, useUpdateAgent, type Agent } from '../queries'
import { ExternalAgentFields } from './ExternalAgentFields'
import { createBody, updateBody, type ExternalValues } from './form'

const resolver = bodyResolver<ExternalValues>(bodySchema('AgentCreate'), createBody)

/** Create an external agent (no `agent`) or change one (with its version; 409: reload,
 *  the input is kept). It works from outside through `/mcp` with its tokens. */
export function ExternalAgentDialog({
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
            {agent ? t('agents.edit.title', { name: agent.name }) : t('agents.external.create')}
          </DialogTitle>
        </DialogHeader>
        {open && (agent ? <EditForm agent={agent} onDone={done} /> : <CreateForm onDone={done} />)}
      </DialogContent>
    </Dialog>
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
  const me = useMe()
  const create = useCreateAgent()
  const form = useForm<ExternalValues>({
    resolver,
    defaultValues: {
      name: '',
      intro: '',
      responsible_user_id: me?.user.id ?? '',
      status: 'draft',
      level: '2',
    },
  })
  const responsible: DirectoryEntry | null = me
    ? { type: 'user', id: me.user.id, name: me.user.name }
    : null
  return (
    <form
      noValidate
      className="flex flex-col gap-4"
      onSubmit={form.handleSubmit((values) =>
        create.mutate(createBody(values), { onSuccess: onDone }),
      )}
    >
      <ExternalAgentFields form={form} responsible={responsible} withLevel />
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
  const form = useForm<ExternalValues>({
    resolver,
    defaultValues: {
      name: agent.name,
      intro: agent.intro,
      responsible_user_id: agent.responsible_user_id,
      status: agent.status,
      level: agent.level === 1 ? '1' : '2',
    },
  })
  const reload = async () => {
    const fresh = await queryClient.fetchQuery({ ...agentQuery(agent.id), staleTime: 0 })
    setVersion(fresh.version)
    update.reset()
  }
  const responsible: DirectoryEntry = {
    type: 'user',
    id: agent.responsible_user_id,
    name: agent.responsible_name ?? t('agents.fields.currentResponsible'),
  }
  return (
    <form
      noValidate
      className="flex flex-col gap-4"
      onSubmit={form.handleSubmit((values) =>
        update.mutate(updateBody(values, version), { onSuccess: onDone }),
      )}
    >
      <ExternalAgentFields form={form} responsible={responsible} withLevel={false} />
      <SaveError error={update.error} onReload={() => void reload()} />
      <Actions pending={update.isPending} submit={t('actions.save')} onDone={onDone} />
    </form>
  )
}
