import { useState } from 'react'
import { sendBrowserTo } from '../browser'
import { useAuthorizeConnector, type ConnectorScope } from '../connectorQueries'
import { safeAuthorizationUrl } from '../display'

/** Connect (or reconnect) an OAuth connector: ask the API for the provider's sign-in
 *  address and send the browser there; it comes back on `/ai/oauth/done`. An address
 *  that is not https is refused here (`unsafe`). */
export function useConnect(scope: ConnectorScope) {
  const authorize = useAuthorizeConnector(scope)
  const [unsafe, setUnsafe] = useState(false)
  const connect = (connectorId: string) => {
    setUnsafe(false)
    authorize.mutate(connectorId, {
      onSuccess: ({ authorization_url }) => {
        const url = safeAuthorizationUrl(authorization_url)
        if (url) sendBrowserTo(url)
        else setUnsafe(true)
      },
    })
  }
  return { connect, pending: authorize.isPending, error: authorize.error, unsafe }
}
