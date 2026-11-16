import type { TFunction } from 'i18next'

/** A code from the backend (`archive.checksum`, `restore.env_missing:HERD_AI_X`,
 *  `restore.safety_backup_failed:backup.dump_failed`) as a sentence; the code itself
 *  when there is no text for it. What follows the first `:` is a detail (a name, a
 *  column with a count, another code) shown as it is. */
export function codeText(t: TFunction, code: string): string {
  const at = code.indexOf(':')
  const base = at < 0 ? code : code.slice(0, at)
  const detail = at < 0 ? '' : code.slice(at + 1)
  const text = t(`backup.codes.${base}`, { detail, defaultValue: '' })
  return text || code
}
