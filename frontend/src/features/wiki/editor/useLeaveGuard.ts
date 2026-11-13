import { useBlocker } from '@tanstack/react-router'

/** Asks before leaving (route change, reload, closing the tab) while `dirty` (a value,
 *  or a function read at the moment of leaving). `question` may be a function, read
 *  when asking. `settle`, if given, runs first when leaving within the app (saving what
 *  can be saved); `dirty` is read again after it, so a settled state leaves without a
 *  question. Reloading or closing the tab cannot wait: it asks while `dirty`. */
export function useLeaveGuard(
  dirty: boolean | (() => boolean),
  question: string | (() => string),
  settle?: () => Promise<void>,
): void {
  const isDirty = typeof dirty === 'function' ? dirty : () => dirty
  const ask = () => window.confirm(typeof question === 'function' ? question() : question)
  useBlocker({
    shouldBlockFn: async () => {
      if (!isDirty()) return false
      if (settle) {
        await settle()
        if (!isDirty()) return false
      }
      return !ask()
    },
    enableBeforeUnload: isDirty,
  })
}
