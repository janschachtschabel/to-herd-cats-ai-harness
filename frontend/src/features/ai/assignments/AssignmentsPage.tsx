import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { EmptyState, ErrorState, LoadingState, PageHeader } from '@/features/shared/states'
import { AiAdminTabs } from '../AiAdminTabs'
import { useAssignments, useGroupAssignments } from '../assignmentQueries'
import { useConnections } from '../queries'
import { DefaultAssignment } from './DefaultAssignment'
import { GroupAssignments } from './GroupAssignments'
import { UserAssignments } from './UserAssignments'

/** Who uses which model (`ai.manage`): person before group before the standard. */
export function AssignmentsPage() {
  const { t } = useTranslation()
  const overview = useAssignments()
  const groups = useGroupAssignments()
  const connections = useConnections()
  // A reload after a conflict starts the edited parts afresh from the server's state.
  const [generation, setGeneration] = useState(0)
  const reload = () => {
    void Promise.all([overview.refetch(), groups.refetch()]).then(() => setGeneration((n) => n + 1))
  }

  const failed = overview.error ?? groups.error ?? connections.error
  return (
    <div>
      <PageHeader title={t('ai.title')} description={t('ai.assignments.description')} />
      <AiAdminTabs />
      {failed ? (
        <ErrorState error={failed} onRetry={reload} />
      ) : !overview.data || groups.isPending || connections.isPending ? (
        <LoadingState />
      ) : connections.items.length === 0 ? (
        <EmptyState text={t('ai.connections.empty')} />
      ) : (
        <div className="flex max-w-3xl flex-col gap-8">
          <DefaultAssignment
            key={`default-${generation}`}
            overview={overview.data}
            connections={connections.items}
            onReload={reload}
          />
          <GroupAssignments
            key={`groups-${generation}`}
            initial={groups.items}
            version={overview.data.version}
            connections={connections.items}
            onReload={reload}
          />
          <UserAssignments connections={connections.items} />
        </div>
      )}
    </div>
  )
}
