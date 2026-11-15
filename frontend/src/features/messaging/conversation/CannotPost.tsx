import { useTranslation } from 'react-i18next'
import type { Conversation } from '@/lib/api'

/** In place of the composer where one may only read: why. */
export function CannotPost({ conversation }: { conversation: Conversation }) {
  const { t } = useTranslation()
  return (
    <p className="border-t pt-3 text-sm text-muted-foreground" role="note">
      {conversation.archived_at
        ? t('messaging.composer.archived')
        : t('messaging.composer.readOnly')}
    </p>
  )
}
