import type { TFunction } from 'i18next'
import type { ActivityEntry } from '@/lib/api'

const PAUSE_REASONS = ['owner', 'failing', 'manual'] as const

/** Why an automation is paused, as one sentence naming its agent (the entry's author);
 *  with no reason left it runs again, and the sentence says so. */
export function automationText(t: TFunction, entry: ActivityEntry): string {
  const agent = entry.author?.name ?? t('messaging.message.unknownAuthor')
  const reason = entry.automation?.paused_reason ?? null
  if (reason === null) return t('activity.automation.resumed', { agent })
  const known = (PAUSE_REASONS as readonly string[]).includes(reason)
  return t(`activity.automation.${known ? reason : 'paused'}`, { agent })
}
