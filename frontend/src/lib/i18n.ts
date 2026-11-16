import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import deAgents from '@/locales/de/agents.json'
import deBackup from '@/locales/de/backup.json'
import deAutomations from '@/locales/de/automations.json'
import deApprovals from '@/locales/de/approvals.json'
import deMcp from '@/locales/de/mcp.json'
import deAi from '@/locales/de/ai.json'
import de from '@/locales/de/common.json'
import deMessaging from '@/locales/de/messaging.json'
import deSignin from '@/locales/de/signin.json'
import deProposals from '@/locales/de/proposals.json'
import deRuns from '@/locales/de/runs.json'
import deSkills from '@/locales/de/skills.json'
import deTickets from '@/locales/de/tickets.json'
import deTokens from '@/locales/de/tokens.json'
import deTotp from '@/locales/de/totp.json'
import deExternal from '@/locales/de/external.json'
import deWiki from '@/locales/de/wiki.json'
import enAgents from '@/locales/en/agents.json'
import enBackup from '@/locales/en/backup.json'
import enAutomations from '@/locales/en/automations.json'
import enApprovals from '@/locales/en/approvals.json'
import enMcp from '@/locales/en/mcp.json'
import enAi from '@/locales/en/ai.json'
import en from '@/locales/en/common.json'
import enMessaging from '@/locales/en/messaging.json'
import enSignin from '@/locales/en/signin.json'
import enProposals from '@/locales/en/proposals.json'
import enRuns from '@/locales/en/runs.json'
import enSkills from '@/locales/en/skills.json'
import enTickets from '@/locales/en/tickets.json'
import enTokens from '@/locales/en/tokens.json'
import enTotp from '@/locales/en/totp.json'
import enExternal from '@/locales/en/external.json'
import enWiki from '@/locales/en/wiki.json'

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

type Tree = { [key: string]: string | Tree }

/** One namespace from several files (`common.json`, `wiki.json`, `messaging.json`,
 *  `tickets.json`, `ai.json`, `agents.json`, `skills.json`, `proposals.json`,
 *  `runs.json`, `approvals.json`, `automations.json`, `mcp.json`, `tokens.json`, `external.json`,
 *  `signin.json`, `backup.json`, `totp.json`): groups such as
 *  `errors` are merged key by key. */
export function mergeResources(...trees: Tree[]): Tree {
  const out: Tree = {}
  for (const tree of trees) {
    for (const [key, value] of Object.entries(tree)) {
      const own = out[key]
      out[key] =
        typeof value === 'object' && typeof own === 'object' ? mergeResources(own, value) : value
    }
  }
  return out
}

void i18n.use(initReactI18next).init({
  resources: {
    de: {
      common: mergeResources(
        de,
        deWiki,
        deMessaging,
        deTickets,
        deAi,
        deAgents,
        deSkills,
        deProposals,
        deRuns,
        deApprovals,
        deAutomations,
        deMcp,
        deTokens,
        deExternal,
        deSignin,
        deBackup,
        deTotp,
      ),
    },
    en: {
      common: mergeResources(
        en,
        enWiki,
        enMessaging,
        enTickets,
        enAi,
        enAgents,
        enSkills,
        enProposals,
        enRuns,
        enApprovals,
        enAutomations,
        enMcp,
        enTokens,
        enExternal,
        enSignin,
        enBackup,
        enTotp,
      ),
    },
  },
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
