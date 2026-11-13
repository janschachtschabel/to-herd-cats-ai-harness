import { Link } from '@tanstack/react-router'
import { Bell, Hash, Plus, UsersRound } from 'lucide-react'
import { lazy, Suspense, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useActivityCount } from '@/features/activity/queries'
import { useMe } from '@/features/auth/queries'
import { canCreateChannelIn, canOpenDm } from '@/features/messaging/abilities'
import { dmLabel } from '@/features/messaging/display'
import { useChannels, useDms, useUnread } from '@/features/messaging/queries'
import { UnreadBadge } from '@/features/messaging/sidebar/UnreadBadge'
import { useSidebarSpaces } from '@/features/spaces/queries'
import { navLinkActive, navLinkClass } from './navStyles'
import { SectionHeading } from './SectionHeading'

const CreateChannelDialog = lazy(() =>
  import('@/features/messaging/CreateChannelDialog').then((m) => ({
    default: m.CreateChannelDialog,
  })),
)
const DmDialog = lazy(() =>
  import('@/features/messaging/DmDialog').then((m) => ({ default: m.DmDialog })),
)

export function ActivitySection() {
  const { t } = useTranslation()
  const count = useActivityCount()
  return (
    <div className="pt-3">
      <Link to="/activity" className={navLinkClass} activeProps={navLinkActive}>
        <Bell className="size-4 shrink-0" aria-hidden />
        <span className="flex-1">{t('nav.activity')}</span>
        {count > 0 && (
          <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1.5 text-[11px] font-semibold text-white tabular-nums">
            <span aria-hidden>{count}</span>
            <span className="sr-only">{t('activity.unreadCount', { count })}</span>
          </span>
        )}
      </Link>
    </div>
  )
}

function Heading({ label, action }: { label: string; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between pr-1">
      <SectionHeading>{label}</SectionHeading>
      {action}
    </div>
  )
}

function AddButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button
      variant="ghost"
      size="icon-xs"
      className="mt-3 text-sidebar-muted-foreground"
      aria-label={label}
      onClick={onClick}
    >
      <Plus aria-hidden />
    </Button>
  )
}

function ListLoading() {
  const { t } = useTranslation()
  return (
    <div role="status" aria-label={t('states.loading')} className="flex flex-col gap-1 px-2">
      <Skeleton className="h-6" />
    </div>
  )
}

export function ChannelsSection() {
  const { t } = useTranslation()
  const channels = useChannels()
  const unread = useUnread()
  const spaces = useSidebarSpaces()
  const [creating, setCreating] = useState(false)
  const names = useMemo(() => new Map(spaces.items.map((s) => [s.id, s.name])), [spaces.items])
  const creatable = spaces.items.filter(canCreateChannelIn)
  const spaceCount = new Set(channels.items.map((c) => c.space_id)).size
  return (
    <>
      <Heading
        label={t('nav.channels')}
        action={
          creatable.length > 0 && (
            <AddButton label={t('messaging.channel.create')} onClick={() => setCreating(true)} />
          )
        }
      />
      {channels.isPending ? (
        <ListLoading />
      ) : channels.isError ? (
        <p className="px-2 text-xs text-destructive">{t('messaging.sidebar.failed')}</p>
      ) : channels.items.length === 0 ? (
        <p className="px-2 text-xs text-sidebar-muted-foreground">
          {t('messaging.sidebar.noChannels')}
        </p>
      ) : (
        <ul className="flex flex-col gap-0.5">
          {channels.items.map((channel) => (
            <li key={channel.id}>
              <Link
                to="/c/$conversationId"
                params={{ conversationId: channel.id }}
                className={navLinkClass}
                activeProps={navLinkActive}
              >
                <Hash className="size-4 shrink-0" aria-hidden />
                <span className="truncate">{channel.name}</span>
                {spaceCount > 1 && channel.space_id && names.has(channel.space_id) && (
                  <span className="truncate text-xs text-sidebar-muted-foreground">
                    {names.get(channel.space_id)}
                  </span>
                )}
                <UnreadBadge unread={unread.get(channel.id)} />
              </Link>
            </li>
          ))}
        </ul>
      )}
      {channels.hasMore && (
        <button type="button" className={navLinkClass} onClick={channels.loadMore}>
          {t('messaging.sidebar.moreChannels')}
        </button>
      )}
      {creating && (
        <Suspense fallback={null}>
          <CreateChannelDialog spaces={creatable} open={creating} onOpenChange={setCreating} />
        </Suspense>
      )}
    </>
  )
}

export function DirectSection() {
  const { t } = useTranslation()
  const me = useMe()
  const dms = useDms()
  const unread = useUnread()
  const [opening, setOpening] = useState(false)
  return (
    <>
      <Heading
        label={t('nav.direct')}
        action={
          canOpenDm(me) && (
            <AddButton label={t('messaging.dm.open')} onClick={() => setOpening(true)} />
          )
        }
      />
      {dms.isPending ? (
        <ListLoading />
      ) : dms.isError ? (
        <p className="px-2 text-xs text-destructive">{t('messaging.sidebar.failed')}</p>
      ) : dms.items.length === 0 ? (
        <p className="px-2 text-xs text-sidebar-muted-foreground">{t('messaging.sidebar.noDms')}</p>
      ) : (
        <ul className="flex flex-col gap-0.5">
          {dms.items.map((dm) => (
            <li key={dm.id}>
              <Link
                to="/c/$conversationId"
                params={{ conversationId: dm.id }}
                className={navLinkClass}
                activeProps={navLinkActive}
              >
                <UsersRound className="size-4 shrink-0" aria-hidden />
                <span className="truncate">{dmLabel(t, dm, me?.user.id)}</span>
                <UnreadBadge unread={unread.get(dm.id)} />
              </Link>
            </li>
          ))}
        </ul>
      )}
      {dms.hasMore && (
        <button type="button" className={navLinkClass} onClick={dms.loadMore}>
          {t('messaging.sidebar.moreDms')}
        </button>
      )}
      {opening && (
        <Suspense fallback={null}>
          <DmDialog open={opening} onOpenChange={setOpening} />
        </Suspense>
      )}
    </>
  )
}
