import { useId, type ReactElement, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/lib/api'
import { errorMessage } from '@/lib/errors'
import { ErrorSmallPrint } from './states'

interface ControlProps {
  id: string
  'aria-invalid'?: boolean
  'aria-describedby'?: string
}

/** A labelled form control with its hint and validation message wired up for screen readers. */
export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string
  hint?: string
  error?: string
  children: (props: ControlProps) => ReactElement
}) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const describedBy = [hint && hintId, error && errorId].filter(Boolean).join(' ') || undefined
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children({ id, 'aria-invalid': error ? true : undefined, 'aria-describedby': describedBy })}
      {hint && (
        <p id={hintId} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}

/** A failed save. A stale version gets the reload hint instead; the form stays as typed. */
export function SaveError({ error, onReload }: { error: unknown; onReload?: () => void }) {
  const { t } = useTranslation()
  if (!error) return null
  if (error instanceof ApiError && error.isVersionConflict) {
    return (
      <Alert>
        <AlertDescription className="flex flex-col gap-2 text-foreground">
          <p>{t('forms.conflict')}</p>
          {onReload && (
            <div>
              <Button type="button" size="sm" variant="outline" onClick={onReload}>
                {t('forms.reload')}
              </Button>
            </div>
          )}
        </AlertDescription>
      </Alert>
    )
  }
  return (
    <Alert variant="destructive">
      <AlertDescription>
        <p className="font-medium text-destructive">{errorMessage(t, error)}</p>
        <ErrorSmallPrint error={error} />
      </AlertDescription>
    </Alert>
  )
}

export function FormActions({ children }: { children: ReactNode }) {
  return <div className="flex justify-end gap-2 pt-2">{children}</div>
}
