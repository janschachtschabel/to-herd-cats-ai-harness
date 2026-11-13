import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { PageHeader } from '@/features/shared/states'
import { SUPPORTED_LOCALES, type Locale } from '@/lib/i18n'
import { PasswordForm } from './PasswordForm'
import { useChangeLocale } from './queries'

/** The person's own settings. */
export function ProfilePage() {
  const { t, i18n } = useTranslation()
  const changeLocale = useChangeLocale()
  const languageId = useId()
  return (
    <div className="max-w-xl">
      <PageHeader title={t('profile.title')} description={t('profile.description')} />
      <section className="flex flex-col gap-2">
        <Label htmlFor={languageId}>{t('profile.language')}</Label>
        <NativeSelect
          id={languageId}
          value={i18n.language}
          onChange={(event) => changeLocale(event.target.value as Locale)}
        >
          {SUPPORTED_LOCALES.map((locale) => (
            <option key={locale} value={locale}>
              {t(`userMenu.locales.${locale}`)}
            </option>
          ))}
        </NativeSelect>
      </section>
      <section className="mt-8 border-t pt-6">
        <PasswordForm />
      </section>
    </div>
  )
}
