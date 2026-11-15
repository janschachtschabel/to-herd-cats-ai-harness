import { useState } from 'react'
import { sendBrowserTo } from '../browser'
import { useAuthorizeConnector, type ConnectorScope } from '../connectorQueries'
import { safeAuthorizationUrl } from '../display'

/** Connect (or reconnect) an OAuth connector: ask the API for the provider's sign-in
 *  address and send the browser there; it comes back on `/ai/oauth/done`. An address
 *  that is not https is refused here (`unsafe`). The browser goes even when the
 *  component asking is gone meanwhile (a just-made connector turns its row into a
 *  card), so this awaits the answer instead of a callback that dies with it. */
export function useConnect(scope: ConnectorScope) {
  const authorize = useAuthorizeConnector(scope)
  const [unsafe, setUnsafe] = useState(false)
  const connect = async (connectorId: string) => {
    setUnsafe(false)
    let answer: { authorization_url: string }
    try {
      answer = await authorize.mutateAsync(connectorId)
    } catch {
      return // shown through `error`
    }
    const url = safeAuthorizationUrl(answer.authorization_url)
    if (url) sendBrowserTo(url)
    else setUnsafe(true)
  }
  return { connect, pending: authorize.isPending, error: authorize.error, unsafe }
}
