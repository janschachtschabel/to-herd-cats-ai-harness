/** What one has typed but not sent, per conversation and thread, in this tab's memory
 *  (gone with the tab, never stored elsewhere). */
const drafts = new Map<string, string>()

export function draftKey(conversationId: string, parentId: string | null): string {
  return `${conversationId}:${parentId ?? ''}`
}

export function getDraft(key: string): string {
  return drafts.get(key) ?? ''
}

export function setDraft(key: string, text: string): void {
  if (text) drafts.set(key, text)
  else drafts.delete(key)
}
