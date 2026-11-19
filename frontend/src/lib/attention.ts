/**
 * Whether a person attends this tab, for the session's idle limit (J7).
 *
 * The server counts every request as a use of the session. Many requests of the app
 * are its own: a refetch after a live event, on an interval or on focus. A request sent
 * while the tab saw no input for more than `IDLE_AFTER_MS` carries
 * `X-Herd-Unattended: 1` (set in `api.ts`) and does not count (R18-1). The other way
 * round, a person who works in the tab without the app asking the API (typing in the
 * live editor) touches the session at most every `TOUCH_EVERY_MS` (R18-4).
 *
 * Input is a pointer press, a key, the wheel, a touch, the window's focus and the tab
 * becoming visible again.
 */

export const IDLE_AFTER_MS = 60_000
export const TOUCH_EVERY_MS = 5 * 60_000
export const UNATTENDED_HEADER = 'X-Herd-Unattended'

const INPUT_EVENTS = ['pointerdown', 'keydown', 'wheel', 'touchstart'] as const

// Loading the app is the person's doing.
let lastInput = Date.now()
let lastAttendedRequest = Date.now()

export function noteInput(at: number = Date.now()): void {
  lastInput = Math.max(lastInput, at)
}

/** No input for more than `IDLE_AFTER_MS`. */
export function isUnattended(at: number = Date.now()): boolean {
  return at - lastInput > IDLE_AFTER_MS
}

/** Note a request that counts as the session's use. */
export function noteAttendedRequest(at: number = Date.now()): void {
  lastAttendedRequest = Math.max(lastAttendedRequest, at)
}

/** The person is here and no counted request went out for `TOUCH_EVERY_MS`. */
export function touchDue(at: number = Date.now()): boolean {
  return !isUnattended(at) && at - lastAttendedRequest >= TOUCH_EVERY_MS
}

/** Marks `request` unattended when nobody gave the tab input lately; otherwise notes it
 *  as a use. The same request object, changed. */
export function markRequest(request: Request, at: number = Date.now()): Request {
  if (isUnattended(at)) request.headers.set(UNATTENDED_HEADER, '1')
  else noteAttendedRequest(at)
  return request
}

/** Listens for the person's input on `win` (once, in the shell); the cleanup. */
export function watchInput(win: Window = window): () => void {
  const onInput = () => noteInput()
  const onVisible = () => {
    if (win.document.visibilityState === 'visible') noteInput()
  }
  const options = { capture: true, passive: true }
  for (const name of INPUT_EVENTS) win.addEventListener(name, onInput, options)
  win.addEventListener('focus', onInput, options)
  win.document.addEventListener('visibilitychange', onVisible, options)
  return () => {
    for (const name of INPUT_EVENTS) win.removeEventListener(name, onInput, options)
    win.removeEventListener('focus', onInput, options)
    win.document.removeEventListener('visibilitychange', onVisible, options)
  }
}

/** Test seam: both times set to `at`. */
export function resetAttention(at: number = Date.now()): void {
  lastInput = at
  lastAttendedRequest = at
}
