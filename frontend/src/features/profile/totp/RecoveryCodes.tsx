import { useTranslation } from 'react-i18next'
import { CopyButton } from '@/features/tokens/CopyButton'

/** Recovery codes, shown once: a list to copy (into a password manager, say). */
export function RecoveryCodes({ codes }: { codes: string[] }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">{t('totp.codes.hint')}</p>
      <ul
        aria-label={t('totp.codes.list')}
        className="grid grid-cols-1 gap-1 rounded-md border bg-muted p-3 font-mono text-sm sm:grid-cols-2"
      >
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <div>
        <CopyButton text={codes.join('\n')} label={t('totp.codes.copy')} />
      </div>
    </div>
  )
}
