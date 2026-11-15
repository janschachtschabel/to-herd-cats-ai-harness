import type { SystemRole } from '@/lib/api'
import { SUPPORTED_LOCALES } from '@/lib/i18n'

export const SYSTEM_ROLES: readonly SystemRole[] = ['owner', 'admin', 'member', 'guest']
export const USER_LOCALES = SUPPORTED_LOCALES
