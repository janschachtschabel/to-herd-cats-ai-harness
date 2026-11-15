import { useTranslation } from 'react-i18next'

/** In pickers, beside an agent's name: "extern", with its meaning for screen readers
 *  (it works from outside through MCP and answers nothing by itself). */
export function ExternalMark() {
  const { t } = useTranslation()
  return (
    <span className="rounded border px-1 text-[11px] leading-4 text-muted-foreground">
      <span aria-hidden>{t('agents.external.mark')}</span>
      <span className="sr-only">{t('agents.external.markTitle')}</span>
    </span>
  )
}
