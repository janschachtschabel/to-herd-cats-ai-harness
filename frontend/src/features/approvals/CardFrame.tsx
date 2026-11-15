import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

const TONES = {
  waiting:
    'border-violet-300 bg-violet-50 text-violet-900 dark:border-violet-500/40 dark:bg-violet-500/15 dark:text-violet-100',
  ok: 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-500/40 dark:bg-emerald-500/15 dark:text-emerald-100',
  off: 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/15 dark:text-amber-100',
} as const

export type Tone = keyof typeof TONES

/** A card's state in words, as a small badge (the words carry the meaning). */
export function CardState({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        TONES[tone],
      )}
    >
      {children}
    </span>
  )
}

/** The frame of a run's card (a release or a question) in a conversation, a thread,
 *  the list of releases or a run's steps. */
export function CardFrame({
  icon,
  title,
  state,
  children,
  label,
}: {
  icon: ReactNode
  title: string
  state?: ReactNode
  children: ReactNode
  label: string
}) {
  return (
    <section
      aria-label={label}
      className="mt-1 flex max-w-xl flex-col gap-2 rounded-lg border bg-card p-3 text-sm text-card-foreground shadow-xs"
    >
      <header className="flex flex-wrap items-center gap-2">
        <span aria-hidden className="text-violet-700 dark:text-violet-300">
          {icon}
        </span>
        <h3 className="min-w-48 flex-1 font-medium">{title}</h3>
        {state}
      </header>
      {children}
    </section>
  )
}
