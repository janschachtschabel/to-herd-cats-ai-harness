import { useCallback, useEffect, useState, type MouseEvent } from 'react'

/** Below Tailwind's `md`: the sidebar would leave the page too little room. */
const NARROW = '(max-width: 767px)'

export function isNarrow(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.(NARROW).matches === true
}

/**
 * Whether the sidebar is open. On a wide screen it starts open beside the page; on a
 * narrow one it starts closed, opens over the page, and closes again with Escape, a
 * click beside it, or a followed link.
 */
export function useSidebar() {
  const [narrow] = useState(isNarrow)
  const [open, setOpen] = useState(!narrow)
  const toggle = useCallback(() => setOpen((value) => !value), [])
  const close = useCallback(() => setOpen(false), [])

  useEffect(() => {
    if (!narrow || !open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [narrow, open])

  /** For the sidebar's clicks: following a link closes it on a narrow screen. */
  const onSidebarClick = useCallback(
    (event: MouseEvent<HTMLElement>) => {
      if (narrow && (event.target as Element).closest('a[href]')) setOpen(false)
    },
    [narrow],
  )

  return { open, narrow, toggle, close, onSidebarClick }
}
