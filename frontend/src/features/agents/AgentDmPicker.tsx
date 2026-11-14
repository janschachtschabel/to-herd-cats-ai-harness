import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { DirectoryCombobox } from '@/features/directory/DirectoryCombobox'
import { Field, SaveError } from '@/features/shared/forms'
import type { DirectoryEntry } from '@/lib/api'
import { useOpenAgentDm } from './queries'

const NONE = new Set<string>()

/** In the direct-message dialog, for people with `ai.use` only: talk to an agent (a
 *  conversation of me and the agent alone). */
export function AgentDmPicker({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const open = useOpenAgentDm()
  const [agent, setAgent] = useState<DirectoryEntry | null>(null)

  const submit = () => {
    if (!agent) return
    open.mutate(agent.id, {
      onSuccess: (dm) => {
        onDone()
        void navigate({ to: '/c/$conversationId', params: { conversationId: dm.id } })
      },
    })
  }

  return (
    <section aria-labelledby="dm-agent-heading" className="flex flex-col gap-3 border-t pt-4">
      <h3 id="dm-agent-heading" className="text-sm font-semibold">
        {t('agents.dm.title')}
      </h3>
      <Field label={t('agents.dm.agent')} hint={t('agents.dm.hint')}>
        {(props) => (
          <DirectoryCombobox
            control={props}
            type="agent"
            selected={agent}
            exclude={NONE}
            onSelect={setAgent}
          />
        )}
      </Field>
      <SaveError error={open.error} />
      <div className="flex justify-end">
        <Button variant="secondary" onClick={submit} disabled={!agent || open.isPending}>
          {t('agents.dm.open')}
        </Button>
      </div>
    </section>
  )
}
