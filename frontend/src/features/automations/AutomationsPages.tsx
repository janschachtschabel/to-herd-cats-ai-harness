import { useTranslation } from 'react-i18next'
import { EmptyState, PageHeader } from '@/features/shared/states'
import { useWiki } from '@/features/wiki/WikiContext'
import { automationAbilities } from './abilities'
import { AutomationList } from './AutomationList'
import { useAgentAutomations, useMyAutomations, useSpaceAutomations } from './queries'

/** "Meine Aufgaben": the automations I own, newest first (people with AI). */
export function MyAutomationsPage() {
  const { t } = useTranslation()
  const list = useMyAutomations()
  return (
    <div>
      <PageHeader
        title={t('automations.mine.title')}
        description={t('automations.mine.description')}
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
  return <SpaceAutomations spaceId={space.id} />
}

function SpaceAutomations({ spaceId }: { spaceId: string }) {
  const { t } = useTranslation()
  const list = useSpaceAutomations(spaceId)
  return (
    <section aria-labelledby="space-automations">
      <div className="mb-4 min-w-0">
        <h2 id="space-automations" className="text-lg font-semibold">
          {t('automations.space.title')}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{t('automations.space.description')}</p>
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
