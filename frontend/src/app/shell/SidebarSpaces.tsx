import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { Skeleton } from '@/components/ui/skeleton'
import { useMe } from '@/features/auth/queries'
import { isOwnPersonal, sidebarSpaces } from '@/features/spaces/display'
import { useSpaces } from '@/features/spaces/queries'
import { SpaceIcon } from '@/features/spaces/SpaceIcon'
import { navLinkActive, navLinkClass } from './navStyles'

export function SidebarSpaces() {
  const { t } = useTranslation()
  const me = useMe()
  const spaces = useSpaces()
  if (spaces.isPending) {
    return (
      <div role="status" aria-label={t('states.loading')} className="flex flex-col gap-1 px-2">
        <Skeleton className="h-6" />
        <Skeleton className="h-6" />
      </div>
    )
  }
  if (spaces.isError) {
    return <p className="px-2 text-xs text-destructive">{t('nav.spacesFailed')}</p>
  }
  const shown = sidebarSpaces(spaces.items, me?.user.id)
  return (
    <ul className="flex flex-col gap-0.5">
      {shown.map((space) => (
        <li key={space.id}>
          <Link
            to="/spaces/$spaceId"
            params={{ spaceId: space.id }}
            className={navLinkClass}
            activeProps={navLinkActive}
          >
            <SpaceIcon space={space} className="size-4" />
            <span className="truncate">
              {isOwnPersonal(space, me?.user.id) ? t('spaces.mine') : space.name}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}
