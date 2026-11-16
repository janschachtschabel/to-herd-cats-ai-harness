import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Field, FormActions, SaveError } from '@/features/shared/forms'

/** Asks for a code before a step on the second factor (turning it off, new recovery
 *  codes); `done` replaces the form once the step has an answer to show. */
export function CodeDialog({
  open,
  title,
  hint,
  label,
  submitLabel,
  destructive = false,
  pending,
  error,
  done,
  onSubmit,
  onOpenChange,
}: {
  open: boolean
  title: string
  hint: string
  label: string
  submitLabel: string
  destructive?: boolean
  pending: boolean
  error: unknown
  done?: React.ReactNode
  onSubmit: (typed: string) => void
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation()
  const [typed, setTyped] = useState('')
  const submit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit(typed.trim())
  }
  const change = (next: boolean) => {
    if (!next) setTyped('')
    onOpenChange(next)
  }
  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{hint}</DialogDescription>
        </DialogHeader>
        {done ?? (
          <form onSubmit={submit} className="flex flex-col gap-4">
            <Field label={label}>
              {(props) => (
                <Input
                  {...props}
                  required
                  autoComplete="one-time-code"
                  spellCheck={false}
                  className="font-mono"
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                />
              )}
            </Field>
            <SaveError error={error} />
            <FormActions>
              <Button type="button" variant="outline" onClick={() => change(false)}>
                {t('actions.cancel')}
              </Button>
              <Button
                type="submit"
                variant={destructive ? 'destructive' : 'default'}
                disabled={pending}
              >
                {submitLabel}
              </Button>
            </FormActions>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
