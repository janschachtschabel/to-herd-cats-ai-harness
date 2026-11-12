import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import de from '@/locales/de/common.json'
import en from '@/locales/en/common.json'

export const SUPPORTED_LOCALES = ['de', 'en'] as const
export type Locale = (typeof SUPPORTED_LOCALES)[number]

const STORAGE_KEY = 'herd.locale'

function storedLocale(): Locale {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    if (value === 'de' || value === 'en') return value
  } catch {
    // storage unavailable: fall back to German
  }
  return 'de'
}

void i18n.use(initReactI18next).init({
  resources: { de: { common: de }, en: { common: en } },
  ns: ['common'],
  defaultNS: 'common',
  lng: storedLocale(),
  fallbackLng: false,
  interpolation: { escapeValue: false },
  initAsync: false,
})
document.documentElement.lang = i18n.language

export function setLocale(locale: Locale): void {
  try {
    localStorage.setItem(STORAGE_KEY, locale)
  } catch {
    // storage unavailable: the choice lasts until reload
  }
  void i18n.changeLanguage(locale)
  document.documentElement.lang = locale
}

export default i18n
