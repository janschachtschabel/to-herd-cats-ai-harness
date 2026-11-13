import {
  Bug,
  CalendarDays,
  CircleCheck,
  Layers,
  SignalHigh,
  SquareCheck,
  UserRound,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { Schemas } from '@/lib/api'
import { formatDay } from '@/lib/format'
import { cn } from '@/lib/utils'
import { CATEGORY_DOT, type Priority, type TicketKind } from './display'

export function StatusBadge({ status }: { status: Schemas['StatusRef'] }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium text-foreground">
      <span
        aria-hidden
        className={cn('size-2 shrink-0 rounded-full', CATEGORY_DOT[status.category])}
      />
      <span className="truncate">{status.name}</span>
    </span>
  )
}

const KIND_ICONS: Record<TicketKind, typeof Bug> = {
  epic: Layers,
  story: CircleCheck,
  task: SquareCheck,
  bug: Bug,
}

export function KindLabel({ kind, iconOnly = false }: { kind: TicketKind; iconOnly?: boolean }) {
  const { t } = useTranslation()
  const Icon = KIND_ICONS[kind]
  const label = t(`tickets.kinds.${kind}`)
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <Icon
        className="size-3.5 shrink-0"
        aria-hidden={!iconOnly}
        aria-label={iconOnly ? label : undefined}
      />
      {!iconOnly && label}
    </span>
  )
}

export function PriorityLabel({ priority }: { priority: Priority }) {
  const { t } = useTranslation()
  const strong = priority === 'urgent' || priority === 'high'
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 text-xs',
        strong ? 'font-medium text-red-700 dark:text-red-400' : 'text-muted-foreground',
      )}
    >
      <SignalHigh className="size-3.5 shrink-0" aria-hidden />
      {t(`tickets.priorities.${priority}`)}
    </span>
  )
}

export function AssigneeLabel({ assignee }: { assignee: Schemas['PersonOut'] | null }) {
  const { t } = useTranslation()
  return (
    <span className="inline-flex min-w-0 items-center gap-1 text-xs text-muted-foreground">
      <UserRound className="size-3.5 shrink-0" aria-hidden />
      <span className="truncate">
        {assignee
          ? (assignee.name ?? t('tickets.fields.unknownPerson'))
          : t('tickets.fields.unassigned')}
      </span>
    </span>
  )
}

export function DueLabel({ due }: { due: string | null }) {
  const { t, i18n } = useTranslation()
  if (!due) return null
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <CalendarDays className="size-3.5 shrink-0" aria-hidden />
      {t('tickets.fields.dueOn', { date: formatDay(due, i18n.language) })}
    </span>
  )
}
