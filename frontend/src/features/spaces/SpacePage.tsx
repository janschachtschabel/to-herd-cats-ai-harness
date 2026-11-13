import { Settings } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/features/shared/states'
import { canEditMembers, canEditSettings } from './display'
import { useSpace } from './queries'
import { SpaceMembers } from './SpaceMembers'
import { SpaceSettingsDialog } from './SpaceSettingsDialog'

/** Members and settings of a space (inside the space's layout, which shows its name). */
export function SpacePage({ spaceId }: { spaceId: string }) {
  const { t } = useTranslation()
  const space = useSpace(spaceId)
  const [editing, setEditing] = useState(false)

  if (space.isPending) return <LoadingState />
  if (space.isError) return <ErrorState error={space.error} onRetry={() => void space.refetch()} />
  const data = space.data

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-xl font-semibold tracking-tight">{t('spaces.settings.page')}</h2>
          {data.description && (
            <p className="mt-1 text-sm text-muted-foreground">{data.description}</p>
          )}
        </div>
        {canEditSettings(data) && (
          <Button variant="outline" onClick={() => setEditing(true)}>
            <Settings aria-hidden />
            {t('spaces.settings.open')}
          </Button>
        )}
      </div>
      <section aria-labelledby="members-heading">
        <h3 id="members-heading" className="mb-3 text-base font-semibold">
          {t('spaces.members.title')}
        </h3>
        {data.kind === 'personal' && (
          <p className="mb-3 text-sm text-muted-foreground">{t('spaces.members.personalFixed')}</p>
        )}
        <SpaceMembers spaceId={spaceId} editable={canEditMembers(data)} />
      </section>
      {canEditSettings(data) && (
        <SpaceSettingsDialog space={data} open={editing} onOpenChange={setEditing} />
      )}
    </div>
  )
}
