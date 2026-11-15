/** One more try for a request the backend asks to send again: 409 with the code
 *  `conflict.retry` (a deadlock it lost, or a row a running agent step held), after
 *  the `Retry-After` seconds it names, at most `MAX_RETRY_WAIT_MS`. Only once: a second
 *  409 is the caller's answer. */
export const MAX_RETRY_WAIT_MS = 2000
const DEFAULT_RETRY_WAIT_MS = 1000

type Fetch = (request: Request) => Promise<Response>
type Sleep = (ms: number) => Promise<void>

const sleep: Sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export function retryingOnConflict(send: Fetch, wait: Sleep = sleep): Fetch {
  return async (request) => {
    const again = request.clone()
    const response = await send(request)
    if (response.status !== 409 || !(await asksForRetry(response))) return response
    await wait(retryWaitMs(response.headers.get('Retry-After')))
    return send(again)
  }
}

async function asksForRetry(response: Response): Promise<boolean> {
  try {
    const body: unknown = await response.clone().json()
    const error = (body as { error?: { code?: unknown } } | null)?.error
    return error?.code === 'conflict.retry'
  } catch {
    return false
  }
}

export function retryWaitMs(header: string | null): number {
  const seconds = header === null ? Number.NaN : Number(header)
  if (!Number.isFinite(seconds) || seconds < 0) return DEFAULT_RETRY_WAIT_MS
  return Math.min(seconds * 1000, MAX_RETRY_WAIT_MS)
}
