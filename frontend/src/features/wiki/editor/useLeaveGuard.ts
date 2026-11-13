import { useBlocker } from '@tanstack/react-router'

/** Asks before leaving (route change, reload, closing the tab) while `dirty`. */
export function useLeaveGuard(dirty: boolean, question: string): void {
  useBlocker({
    shouldBlockFn: () => dirty && !window.confirm(question),
    enableBeforeUnload: () => dirty,
  })
}
