import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ErrorSmallPrint } from '@/features/shared/states'
import { ApiError } from '@/lib/api'
import { errorMessage } from '@/lib/errors'

/** A failed wiki action. A 409 version conflict says that the current page has been
 *  loaded (the mutation refetched it) and the step can be tried again. */
export function WikiError({ error }: { error: unknown }) {
  const { t } = useTranslation()
  if (!error) return null
  if (error instanceof ApiError && error.isVersionConflict) {
    return (
      <Alert>
        <AlertDescription className="text-foreground">
          {t('wiki.conflict.reloaded')}
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
