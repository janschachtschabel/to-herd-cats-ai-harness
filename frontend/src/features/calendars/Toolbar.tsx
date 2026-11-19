import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { VIEWS, type CalendarView } from './dates'

/** Today, back and on, the period's name, the view, and a title search. */
export function Toolbar({
  view,
  title,
  query,
  onToday,
  onStep,
  onView,
  onQuery,
}: {
  view: CalendarView
  title: string
  query: string
  onToday: () => void
  onStep: (step: 1 | -1) => void
  onView: (view: CalendarView) => void
  onQuery: (query: string) => void
}) {
  const { t } = useTranslation()
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <div
        role="group"
        aria-label={t('calendar.toolbar.label')}
        className="flex items-center gap-1"
      >
        <Button variant="outline" onClick={onToday}>
          {t('calendar.toolbar.today')}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label={t('calendar.toolbar.previous')}
          onClick={() => onStep(-1)}
        >
          <ChevronLeft aria-hidden />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label={t('calendar.toolbar.next')}
          onClick={() => onStep(1)}
        >
          <ChevronRight aria-hidden />
        </Button>
      </div>
      <h2 className="flex-1 text-lg font-semibold whitespace-nowrap" aria-live="polite">
        {title}
      </h2>
      <div className="relative">
        <Search
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-2 size-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          type="search"
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          aria-label={t('calendar.toolbar.search')}
          placeholder={t('calendar.toolbar.search')}
          className="w-48 pl-8"
          maxLength={300}
        />
      </div>
      <div
        role="group"
        aria-label={t('calendar.views.label')}
        className="flex rounded-lg border p-0.5"
      >
        {VIEWS.map((option) => (
          <button
            key={option}
            type="button"
            aria-pressed={option === view}
            onClick={() => onView(option)}
            className={cn(
              'rounded-md px-2.5 py-1 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
              option === view
                ? 'bg-primary font-medium text-primary-foreground'
                : 'text-foreground hover:bg-muted',
            )}
          >
            {t(`calendar.views.${option}`)}
          </button>
        ))}
      </div>
    </div>
  )
}
