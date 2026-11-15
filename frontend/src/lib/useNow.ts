import { useEffect, useState } from 'react'

/** The time now, taken when first shown and again every `everyMs` (null: never). */
export function useNow(everyMs: number | null = null): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (everyMs === null) return
    const timer = setInterval(() => setNow(Date.now()), everyMs)
    return () => clearInterval(timer)
  }, [everyMs])
  return now
}
