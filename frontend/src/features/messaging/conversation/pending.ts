import { useMemo, useSyncExternalStore } from 'react'

/** A message on its way (or that did not get there), kept in this tab only. Its
 *  `clientId` is sent along, so sending again cannot post it twice. */
export interface PendingMessage {
  clientId: string
  conversationId: string
  parentId: string | null
  body: string
  mentions: string[]
  status: 'sending' | 'failed'
  error: unknown
  createdAt: string
}

let pending: readonly PendingMessage[] = []
const listeners = new Set<() => void>()

function publish(next: readonly PendingMessage[]): void {
  pending = next
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function addPending(message: PendingMessage): void {
  publish([...pending.filter((p) => p.clientId !== message.clientId), message])
}

export function updatePending(clientId: string, change: Partial<PendingMessage>): void {
  publish(pending.map((p) => (p.clientId === clientId ? { ...p, ...change } : p)))
}

export function removePending(clientId: string): void {
  publish(pending.filter((p) => p.clientId !== clientId))
}

export function getPending(clientId: string): PendingMessage | undefined {
  return pending.find((p) => p.clientId === clientId)
}

/** For tests: forget everything. */
export function clearPending(): void {
  publish([])
}

/** The pending messages of one conversation (top level) or one thread. */
export function usePending(conversationId: string, parentId: string | null): PendingMessage[] {
  const all = useSyncExternalStore(subscribe, () => pending)
  return useMemo(
    () => all.filter((p) => p.conversationId === conversationId && p.parentId === parentId),
    [all, conversationId, parentId],
  )
}
