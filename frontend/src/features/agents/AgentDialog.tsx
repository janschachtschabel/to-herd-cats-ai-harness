import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { chatConnections, type Connection } from '@/features/ai/display'
import { hasPermission, useMe } from '@/features/auth/queries'
import { FormActions, SaveError } from '@/features/shared/forms'
import type { DirectoryEntry, Schemas } from '@/lib/api'
import { bodySchema } from '@/lib/schemas'
import { AgentFields } from './AgentFields'
import { useUsers } from '@/features/admin/users/queries'
import { agentQuery, useCreateAgent, useUpdateAgent, type Agent } from './queries'

type Values = Schemas['AgentCreate']
const schema = bodySchema('AgentCreate')

/** Create an agent (no `agent`) or change one (with its version; 409 on a stale one). */
export function AgentDialog({
  open,
  agent,
  connections,
  onOpenChange,
}: {
  open: boolean
  agent?: Agent
  connections: readonly Connection[]
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const done = () => onOpenChange(false)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {agent ? t('agents.edit.title', { name: agent.name }) : t('agents.create.title')}
          </DialogTitle>
        </DialogHeader>
        {open &&
          (agent ? (
            <EditForm agent={agent} connections={connections} onDone={done} />
          ) : (
            <CreateForm connections={connections} onDone={done} />
          ))}
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

function CreateForm({
  connections,
  onDone,
}: {
  connections: readonly Connection[]
  onDone: () => void
}) {
  const { t } = useTranslation()
  const me = useMe()
  const create = useCreateAgent()
  const first = chatConnections(connections)[0]
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: '',
      intro: '',
      instructions: '',
      connection_id: first?.id ?? '',
      model: first?.models[0] ?? '',
      responsible_user_id: me?.user.id ?? '',
      status: 'draft',
      max_steps: 25,
      max_runtime_seconds: 600,
    },
  })
  const responsible: DirectoryEntry | null = me
    ? { type: 'user', id: me.user.id, name: me.user.name }
    : null
  return (
    <form
      onSubmit={form.handleSubmit((values) => create.mutate(values, { onSuccess: onDone }))}
      noValidate
      className="flex flex-col gap-4"
    >
      <AgentFields form={form} connections={connections} responsible={responsible} />
      <SaveError error={create.error} />
      <Actions pending={create.isPending} submit={t('agents.create.submit')} onDone={onDone} />
    </form>
  )
}

function EditForm({
  agent,
  connections,
  onDone,
}: {
  agent: Agent
  connections: readonly Connection[]
  onDone: () => void
}) {
  const { t } = useTranslation()
  const me = useMe()
  const queryClient = useQueryClient()
  const update = useUpdateAgent(agent.id)
  const [version, setVersion] = useState(agent.version)
  // The person's name, from the people list where one may read it (the agent names
  // only the id); otherwise a placeholder until another person is picked.
  const people = useUsers(hasPermission(me, 'user.manage'))
  const name = people.items.find((u) => u.id === agent.responsible_user_id)?.name ?? null
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: agent.name,
      intro: agent.intro,
      instructions: agent.instructions,
      connection_id: agent.connection_id,
      model: agent.model,
      responsible_user_id: agent.responsible_user_id,
      status: agent.status,
      max_steps: agent.max_steps,
      max_runtime_seconds: agent.max_runtime_seconds,
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
    name: name ?? t('agents.fields.currentResponsible'),
  }
  return (
    <form
      onSubmit={form.handleSubmit((values) =>
        update.mutate({ ...values, version }, { onSuccess: onDone }),
      )}
      noValidate
      className="flex flex-col gap-4"
    >
      <AgentFields
        key={name ?? 'unnamed'}
        form={form}
        connections={connections}
        responsible={responsible}
      />
      <SaveError error={update.error} onReload={() => void reload()} />
      <Actions pending={update.isPending} submit={t('actions.save')} onDone={onDone} />
    </form>
  )
}
