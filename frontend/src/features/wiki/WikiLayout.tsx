import { Link, Outlet } from '@tanstack/react-router'
import { FilePlus, Settings, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/queries'
import { ErrorState, LoadingState } from '@/features/shared/states'
import { isOwnPersonal } from '@/features/spaces/display'
import { useSpace } from '@/features/spaces/queries'
import { SpaceIcon } from '@/features/spaces/SpaceIcon'
import type { Space } from '@/lib/api'
import { wikiAbilities } from './abilities'
import { NewPageDialog } from './NewPageDialog'
import { PageTree } from './PageTree'
import { useTree } from './queries'
import { SpaceTransferMenu } from './transfer/SpaceTransferMenu'
import { titleLookup, WikiContext, type Wiki } from './WikiContext'

/** A space: its page tree on the left, the page (or trash, settings) on the right. */
export function WikiLayout({ spaceId }: { spaceId: string }) {
  const space = useSpace(spaceId)
  if (space.isPending) return <LoadingState />
  if (space.isError) return <ErrorState error={space.error} onRetry={() => void space.refetch()} />
  return <WikiFrame space={space.data} />
}

function WikiFrame({ space }: { space: Space }) {
  const { t } = useTranslation()
  const me = useMe()
  const tree = useTree(space.id)
  const [creating, setCreating] = useState<{ title?: string; parentId?: string | null } | null>(
    null,
  )
  const nodes = useMemo(() => tree.data ?? [], [tree.data])
  const wiki: Wiki = useMemo(
    () => ({
      space,
      me,
      abilities: wikiAbilities(space, me),
      nodes,
      titles: titleLookup(nodes),
      createPage: (initial) => setCreating(initial ?? {}),
    }),
    [space, me, nodes],
  )
  const { abilities } = wiki

  return (
    <WikiContext.Provider value={wiki}>
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <SpaceIcon space={space} className="size-5" />
            <Link to="/spaces/$spaceId" params={{ spaceId: space.id }} className="truncate">
              {isOwnPersonal(space, me?.user.id) ? t('spaces.mine') : space.name}
            </Link>
          </h1>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge variant="outline">{t(`spaces.kinds.${space.kind}.label`)}</Badge>
            {space.my_role && (
              <Badge variant="secondary">
                {t('spaces.myRole', { role: t(`roles.${space.my_role}`) })}
              </Badge>
            )}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {abilities.trash && (
            <Button variant="outline" asChild>
              <Link to="/spaces/$spaceId/trash" params={{ spaceId: space.id }}>
                <Trash2 aria-hidden />
                {t('wiki.trash.open')}
              </Link>
            </Button>
          )}
          <Button variant="outline" asChild>
            <Link to="/spaces/$spaceId/settings" params={{ spaceId: space.id }}>
              <Settings aria-hidden />
              {t('wiki.space.settings')}
            </Link>
          </Button>
          <SpaceTransferMenu />
        </div>
      </header>
      <div className="grid gap-6 md:grid-cols-[14rem_minmax(0,1fr)]">
        <aside aria-labelledby="wiki-tree-heading" className="min-w-0">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 id="wiki-tree-heading" className="text-sm font-semibold">
              {t('wiki.tree.title')}
            </h2>
            {abilities.create && (
              <Button size="sm" variant="ghost" onClick={() => setCreating({})}>
                <FilePlus aria-hidden />
                {t('wiki.create.open')}
              </Button>
            )}
          </div>
          {tree.isPending ? (
            <LoadingState rows={3} />
          ) : tree.isError ? (
            <ErrorState error={tree.error} onRetry={() => void tree.refetch()} />
          ) : nodes.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('wiki.tree.empty')}</p>
          ) : (
            <PageTree spaceId={space.id} nodes={nodes} />
          )}
        </aside>
        <div className="min-w-0">
          <Outlet />
        </div>
      </div>
      {abilities.create && (
        <NewPageDialog
          open={creating !== null}
          initial={creating ?? {}}
          onOpenChange={(open) => !open && setCreating(null)}
        />
      )}
    </WikiContext.Provider>
  )
}
