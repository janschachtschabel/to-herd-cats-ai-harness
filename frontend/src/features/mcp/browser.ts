/** Leaves the app for the provider's sign-in page (its own module, so tests can see
 *  where the browser would go). */
export function sendBrowserTo(url: string): void {
  window.location.assign(url)
}
