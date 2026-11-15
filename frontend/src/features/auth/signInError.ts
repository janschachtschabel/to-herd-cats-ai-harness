import { useTranslation } from 'react-i18next'

/** The text for a sign-in or link that came back refused (`?error=oidc.<reason>`). */
export function useSignInError(code: string | undefined): string | null {
  const { t } = useTranslation()
  if (!code) return null
  const reason = code.replace(/^oidc\./, '')
  return t(`signin.errors.${reason}`, { defaultValue: t('signin.failed') })
}
