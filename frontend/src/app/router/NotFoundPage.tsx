import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  const { t } = useTranslation()
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 py-24 text-center">
      <h1 className="text-xl font-semibold">{t('notFound.title')}</h1>
      <p className="text-sm text-muted-foreground">{t('notFound.text')}</p>
      <Button asChild variant="outline">
        <Link to="/spaces">{t('notFound.back')}</Link>
      </Button>
    </div>
  )
}
