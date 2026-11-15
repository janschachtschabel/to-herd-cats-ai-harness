import { useTranslation } from 'react-i18next'
import { CopyButton } from '@/features/tokens/CopyButton'

/** Where the provider sends people back, to copy into its settings; without
 *  HERD_PUBLIC_URL there is none, and it says why. */
export function Callback({ url }: { url: string | null }) {
  const { t } = useTranslation()
  if (!url) return <p className="text-xs text-destructive">{t('oidcAdmin.callbackMissing')}</p>
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <div className="flex flex-wrap items-center gap-2">
        <code className="rounded bg-muted px-1.5 py-0.5 text-xs break-all">{url}</code>
        <CopyButton text={url} label={t('oidcAdmin.copy')} />
      </div>
      <p className="text-xs text-muted-foreground">{t('oidcAdmin.callbackHint')}</p>
    </div>
  )
}
