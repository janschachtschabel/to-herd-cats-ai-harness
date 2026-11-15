import { BookOpen, Lock, UsersRound } from 'lucide-react'
import type { Space, SpaceKind } from '@/lib/api'
import { cn } from '@/lib/utils'

const KIND_ICONS: Record<SpaceKind, typeof BookOpen> = {
  open: BookOpen,
  team: UsersRound,
  personal: Lock,
}

/** The space's own emoji if it has one, else the icon of its kind (spec 6.2). */
export function SpaceIcon({ space, className }: { space: Space; className?: string }) {
  if (space.icon) {
    return (
      <span
        aria-hidden
        className={cn('inline-flex shrink-0 items-center justify-center leading-none', className)}
      >
        {space.icon}
      </span>
    )
  }
  const Icon = KIND_ICONS[space.kind]
  return <Icon aria-hidden className={cn('shrink-0', className)} />
}
