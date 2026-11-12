import { Link } from '@tanstack/react-router'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useMe, usePermission } from '@/features/auth/queries'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import type { Space } from '@/lib/api'
import { CreateSpaceDialog } from './CreateSpaceDialog'
import { groupByKind, isOwnPersonal } from './display'
import { useSpaces } from './queries'
import { SpaceIcon } from './SpaceIcon'

function SpaceRow({ space, own }: { space: Space; own: boolean }) {
  const { t } = useTranslation()
  return (
    <li>
      <Link
        to="/spaces/$spaceId"
        params={{ spaceId: space.id }}
        className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3 transition-colors hover:bg-accent"
      >
        <span className="flex size-9 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <SpaceIcon space={space} className="size-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{own ? t('spaces.mine') : space.name}</span>
          {space.description && (
            <span className="block truncate text-sm text-muted-foreground">
              {space.description}
            </span>
          )}
        </span>
        {space.my_role && <Badge variant="secondary">{t(`roles.${space.my_role}`)}</Badge>}
      </Link>
    </li>
  )
}

export function SpacesPage() {
  const { t } = useTranslation()
  const me = useMe()
  const canCreate = usePermission('space.create')
  const spaces = useSpaces()
  const [creating, setCreating] = useState(false)

  return (
    <div>
      <PageHeader
        title={t('spaces.title')}
        description={t('spaces.description')}
        actions={
          canCreate && (
            <Button onClick={() => setCreating(true)}>
              <Plus aria-hidden />
              {t('spaces.create.open')}
            </Button>
          )
        }
      />
      {spaces.isPending ? (
        <LoadingState />
      ) : spaces.isError ? (
        <ErrorState error={spaces.error} onRetry={() => void spaces.refetch()} />
      ) : spaces.items.length === 0 ? (
        <EmptyState text={t('spaces.empty')} />
      ) : (
        <div className="flex flex-col gap-8">
          {groupByKind(spaces.items, me?.user.id).map((group) => (
            <section key={group.kind} aria-labelledby={`kind-${group.kind}`}>
              <h2 id={`kind-${group.kind}`} className="mb-1 text-sm font-semibold">
                {t(`spaces.kinds.${group.kind}.plural`)}
              </h2>
              <p className="mb-3 text-sm text-muted-foreground">
                {t(`spaces.kinds.${group.kind}.hint`)}
              </p>
              <ul className="grid gap-2 sm:grid-cols-2">
                {group.spaces.map((space) => (
                  <SpaceRow key={space.id} space={space} own={isOwnPersonal(space, me?.user.id)} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
      <LoadMore hasMore={spaces.hasMore} loading={spaces.loadingMore} onLoad={spaces.loadMore} />
      <CreateSpaceDialog open={creating} onOpenChange={setCreating} />
    </div>
  )
}
