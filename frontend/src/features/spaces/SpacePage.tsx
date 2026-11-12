import { Settings } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/queries'
import { ErrorState, LoadingState, PageHeader } from '@/features/shared/states'
import { canEditMembers, canEditSettings, isOwnPersonal } from './display'
import { useSpace } from './queries'
import { SpaceIcon } from './SpaceIcon'
import { SpaceMembers } from './SpaceMembers'
import { SpaceSettingsDialog } from './SpaceSettingsDialog'

export function SpacePage({ spaceId }: { spaceId: string }) {
  const { t } = useTranslation()
  const me = useMe()
  const space = useSpace(spaceId)
  const [editing, setEditing] = useState(false)

  if (space.isPending) return <LoadingState />
  if (space.isError) return <ErrorState error={space.error} onRetry={() => void space.refetch()} />
  const data = space.data
  const own = isOwnPersonal(data, me?.user.id)

  return (
    <div>
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <SpaceIcon space={data} className="size-5" />
            {own ? t('spaces.mine') : data.name}
          </span>
        }
        description={data.description ?? undefined}
        actions={
          canEditSettings(data) && (
            <Button variant="outline" onClick={() => setEditing(true)}>
              <Settings aria-hidden />
              {t('spaces.settings.open')}
            </Button>
          )
        }
      >
        <div className="mt-3 flex flex-wrap gap-2">
          <Badge variant="outline">{t(`spaces.kinds.${data.kind}.label`)}</Badge>
          {data.my_role && (
            <Badge variant="secondary">
              {t('spaces.myRole', { role: t(`roles.${data.my_role}`) })}
            </Badge>
          )}
        </div>
      </PageHeader>
      <section aria-labelledby="members-heading">
        <h2 id="members-heading" className="mb-3 text-base font-semibold">
          {t('spaces.members.title')}
        </h2>
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
