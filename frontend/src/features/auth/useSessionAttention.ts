import { useEffect } from 'react'
import { touchDue, watchInput } from '@/lib/attention'
import { touchSession } from './queries'

// How often the tab looks whether a touch is due.
export const TOUCH_CHECK_MS = 30_000

/** Watches the person's input in this tab and touches the session while she works in
 *  it without the app asking the API (R18-4). Mount once, in the shell. */
export function useSessionAttention(): void {
  useEffect(() => {
    const stop = watchInput()
    const timer = window.setInterval(() => {
      if (touchDue()) void touchSession().catch(() => undefined)
    }, TOUCH_CHECK_MS)
    return () => {
      stop()
      window.clearInterval(timer)
    }
  }, [])
}
