import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'

/** Copies `text` to the clipboard; says "copied" until the text changes. `label` names
 *  what is copied for screen readers ("Token kopieren"). */
export function CopyButton({ text, label }: { text: string; label: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState<string | null>(null)
  const done = copied === text
  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      aria-label={label}
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => setCopied(text))
      }}
    >
      {done ? <Check aria-hidden /> : <Copy aria-hidden />}
      <span aria-live="polite">{done ? t('tokens.copy.done') : t('tokens.copy.label')}</span>
    </Button>
  )
}
