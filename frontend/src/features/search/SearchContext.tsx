import { createContext, useContext } from 'react'

/** Opens the search palette (sidebar button, Ctrl+K). */
export const SearchContext = createContext<() => void>(() => {})

export function useOpenSearch(): () => void {
  return useContext(SearchContext)
}
