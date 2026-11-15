import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { EmptyState, PageHeader } from '@/features/shared/states'
import { useMe } from '@/features/auth/queries'
import type { Space } from '@/lib/api'
import { useWiki } from '@/features/wiki/WikiContext'
import { automationAbilities } from './abilities'
import { AutomationFormDialog } from './AutomationFormDialog'
import { AutomationList } from './AutomationList'
import { useAgentAutomations, useMyAutomations, useSpaceAutomations } from './queries'

/** "Meine Aufgaben": the automations I own, newest first (people with AI). */
export function MyAutomationsPage() {
  const { t } = useTranslation()
  const list = useMyAutomations()
  const abilities = automationAbilities(useMe(), null)
  return (
    <div>
      <PageHeader
        title={t('automations.mine.title')}
        description={t('automations.mine.description')}
        actions={abilities.create && <NewAutomation />}
      />
      <AutomationList list={list} emptyText={t('automations.mine.empty')} />
    </div>
  )
}

/** A space's automations: those at its channels and tickets that the API shows me
 *  (my own, and all of them to who manages the space). */
export function SpaceAutomationsView() {
  const { t } = useTranslation()
  const { space, me } = useWiki()
  const abilities = automationAbilities(me, space)
  if (!abilities.list) return <EmptyState text={t('automations.detail.notFound')} />
  return <SpaceAutomations space={space} create={abilities.create} eventRules={abilities.event} />
}

/** "Neue Aufgabe" and its form (in a space: its places, event rules for managers). */
function NewAutomation({
  space = null,
  eventRules = false,
}: {
  space?: Space | null
  eventRules?: boolean
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <Plus aria-hidden />
        {t('automations.create')}
      </Button>
      <AutomationFormDialog
        open={open}
        onOpenChange={setOpen}
        space={space}
        eventRules={eventRules}
      />
    </>
  )
}

function SpaceAutomations({
  space,
  create,
  eventRules,
}: {
  space: Space
  create: boolean
  eventRules: boolean
}) {
  const { t } = useTranslation()
  const list = useSpaceAutomations(space.id)
  return (
    <section aria-labelledby="space-automations">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="space-automations" className="text-lg font-semibold">
            {t('automations.space.title')}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">{t('automations.space.description')}</p>
        </div>
        {create && <NewAutomation space={space} eventRules={eventRules} />}
      </div>
      <AutomationList list={list} emptyText={t('automations.space.empty')} showOwner />
    </section>
  )
}

/** An agent's automations in its administration (`agent.manage`). */
export function AgentAutomationsPanel({ agentId }: { agentId: string }) {
  const { t } = useTranslation()
  const list = useAgentAutomations(agentId)
  return (
    <section aria-labelledby="agent-automations" className="flex flex-col gap-3">
      <div>
        <h2 id="agent-automations" className="text-base font-semibold">
          {t('automations.agent.title')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('automations.agent.description')}</p>
      </div>
      <AutomationList list={list} emptyText={t('automations.agent.empty')} showOwner />
    </section>
  )
}
