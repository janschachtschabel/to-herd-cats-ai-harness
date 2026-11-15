import { useTranslation } from 'react-i18next'

/** Beside the AI mark of something written through an access token at `/mcp` (plan
 *  M8): the token's name as it was then (`via_token`). */
export function ViaToken({ name }: { name: string }) {
  const { t } = useTranslation()
  return <span className="text-xs text-muted-foreground">{t('tokens.via', { name })}</span>
}
