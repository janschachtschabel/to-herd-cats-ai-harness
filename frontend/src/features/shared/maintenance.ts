import { useQuery } from '@tanstack/react-query'
import { useSyncExternalStore } from 'react'
import { api, unwrap } from '@/lib/api'

/** Whether this tab shows the maintenance page: set when any request was answered 503
 *  `maintenance.active`, or when an owner started a replace and maintenance began. */
let shown = false
const listeners = new Set<() => void>()

export function showMaintenance(): void {
  if (shown) return
  shown = true
  for (const listener of listeners) listener()
}

/** For tests: back to the app. */
export function resetMaintenance(): void {
  shown = false
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useMaintenanceShown(): boolean {
  return useSyncExternalStore(subscribe, () => shown)
}

export const MAINTENANCE_POLL_MS = 3_000

/** Leaves the page for a fresh start (the session is gone after a replace: login). */
export const reload = { to: (path: string) => window.location.assign(path) }

/** `GET /api/maintenance` (open in maintenance, no session needed), every few seconds
 *  while `polling`. */
export function useMaintenanceState(polling: boolean) {
  return useQuery({
    queryKey: ['maintenance'],
    queryFn: async () => unwrap(await api.GET('/api/maintenance')),
    refetchInterval: polling ? MAINTENANCE_POLL_MS : false,
    enabled: polling,
  })
}
