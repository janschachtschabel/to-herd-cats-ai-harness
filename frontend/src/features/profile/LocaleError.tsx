import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/errors'
import { useLocaleError } from './queries'

/** Says so when a language change could not be stored (the language came back). */
export function LocaleError() {
  const { t } = useTranslation()
  const { error, dismiss } = useLocaleError()
  if (!error) return null
  return (
    <Alert variant="destructive" className="mb-6">
      <AlertTitle>{t('profile.localeNotSaved')}</AlertTitle>
      <AlertDescription>{errorMessage(t, error)}</AlertDescription>
      <AlertAction>
        <Button variant="ghost" size="icon" aria-label={t('actions.close')} onClick={dismiss}>
          <X aria-hidden />
        </Button>
      </AlertAction>
    </Alert>
  )
}
