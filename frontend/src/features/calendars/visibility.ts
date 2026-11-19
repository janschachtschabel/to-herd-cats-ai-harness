import { useCallback, useState } from 'react'

const STORE = 'herd.calendars.hidden'

function read(): Set<string> {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(STORE) ?? '[]')
    return new Set(Array.isArray(stored) ? stored.filter((v) => typeof v === 'string') : [])
  } catch {
    return new Set()
  }
}

/** The calendars this browser hides (the list's switches); kept in this browser only,
 *  as a view setting, never sent beyond the window's `calendar_ids`. */
export function useHiddenCalendars() {
  const [hidden, setHidden] = useState(read)
  const toggle = useCallback((calendarId: string) => {
    setHidden((before) => {
      const next = new Set(before)
      if (!next.delete(calendarId)) next.add(calendarId)
      localStorage.setItem(STORE, JSON.stringify([...next]))
      return next
    })
  }, [])
  return { hidden, toggle }
}
