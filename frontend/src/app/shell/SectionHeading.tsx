import type { ReactNode } from 'react'

export function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="px-2 pt-4 pb-1 text-xs font-medium tracking-wide text-sidebar-muted-foreground uppercase">
      {children}
    </h2>
  )
}
