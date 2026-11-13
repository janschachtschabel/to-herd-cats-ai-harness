import { useBlocker } from '@tanstack/react-router'

/** Asks before leaving (route change, reload, closing the tab) while `dirty` (a value,
 *  or a function read at the moment of leaving). */
export function useLeaveGuard(dirty: boolean | (() => boolean), question: string): void {
  const isDirty = typeof dirty === 'function' ? dirty : () => dirty
  useBlocker({
    shouldBlockFn: () => isDirty() && !window.confirm(question),
    enableBeforeUnload: isDirty,
  })
}
