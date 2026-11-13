/** Minutes left until `iso`, rounded up; 0 once it has passed. */
export function minutesLeft(iso: string, now: number): number {
  return Math.max(0, Math.ceil((new Date(iso).getTime() - now) / 60_000))
}
