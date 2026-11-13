import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { SearchContext } from './SearchContext'

const CommandPalette = lazy(() =>
  import('./CommandPalette').then((m) => ({ default: m.CommandPalette })),
)

/** Holds the palette: Ctrl+K (Cmd+K) anywhere opens it, as does `useOpenSearch()`. */
export function SearchProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  return (
    <SearchContext.Provider value={() => setOpen(true)}>
      {children}
      {open && (
        <Suspense fallback={null}>
          <CommandPalette open={open} onOpenChange={setOpen} />
        </Suspense>
      )}
    </SearchContext.Provider>
  )
}
