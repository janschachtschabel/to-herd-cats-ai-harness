import { useId, useState, type ComponentProps } from 'react'
import { useTranslation } from 'react-i18next'
import { Textarea } from '@/components/ui/textarea'
import { MarkdownContent } from '@/features/wiki/MarkdownContent'
import { cn } from '@/lib/utils'

const TABS = ['write', 'preview'] as const
type Tab = (typeof TABS)[number]

/** A Markdown text with a preview, as the wiki renders it (GFM, never raw HTML). The
 *  textarea stays mounted while previewing, so the form keeps its value and focus
 *  order. Arrow keys move between the two tabs. */
export function MarkdownField({
  label,
  value,
  error,
  textarea,
}: {
  label: string
  value: string
  error?: string
  textarea: ComponentProps<'textarea'>
}) {
  const { t } = useTranslation()
  const id = useId()
  const [tab, setTab] = useState<Tab>('write')
  const select = (next: Tab) => {
    setTab(next)
    document.getElementById(`${id}-${next}`)?.focus()
  }
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <label htmlFor={`${id}-text`} className="text-sm font-medium">
          {label}
        </label>
        <div role="tablist" aria-label={t('skills.editor.tabs', { label })} className="flex gap-1">
          {TABS.map((name) => (
            <button
              key={name}
              id={`${id}-${name}`}
              type="button"
              role="tab"
              aria-selected={tab === name}
              aria-controls={`${id}-${name}-panel`}
              tabIndex={tab === name ? 0 : -1}
              onClick={() => setTab(name)}
              onKeyDown={(e) => {
                if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                  e.preventDefault()
                  select(name === 'write' ? 'preview' : 'write')
                }
              }}
              className={cn(
                'rounded-md px-2 py-1 text-xs focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                tab === name ? 'bg-muted font-medium' : 'text-muted-foreground',
              )}
            >
              {t(`skills.editor.${name}`)}
            </button>
          ))}
        </div>
      </div>
      <div id={`${id}-write-panel`} role="tabpanel" hidden={tab !== 'write'}>
        <Textarea
          id={`${id}-text`}
          rows={12}
          className="font-mono text-xs"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          {...textarea}
        />
      </div>
      <div
        id={`${id}-preview-panel`}
        role="tabpanel"
        hidden={tab !== 'preview'}
        className="min-h-32 rounded-lg border p-3"
      >
        {value.trim() === '' ? (
          <p className="text-sm text-muted-foreground">{t('skills.editor.empty')}</p>
        ) : (
          tab === 'preview' && <MarkdownContent spaceId="" markdown={value} />
        )}
      </div>
      {error && (
        <p id={`${id}-error`} className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
