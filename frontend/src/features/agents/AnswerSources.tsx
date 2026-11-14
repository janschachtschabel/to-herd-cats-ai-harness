import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/queries'
import { usesAi } from '@/features/ai/display'
import { RunLink } from '@/features/runs/RunBits'
import { pageQuery } from '@/features/wiki/queries'
import { keyNumber } from '@/features/tickets/refs'
import { errorMessage } from '@/lib/errors'
import { sourcesOf, type Source } from './display'
import { useRunEvents } from './queries'

/** Under an agent's answer: the pages and tickets its run read, loaded when asked
 *  (the run's steps are readable by whom it concerns; others see nothing), and a link
 *  to the run. A result from a space the reader may not read comes redacted and is
 *  only counted. */
export function AnswerSources({ runId }: { runId: string }) {
  const { t } = useTranslation()
  const me = useMe()
  const [open, setOpen] = useState(false)
  const events = useRunEvents(runId, open)
  if (!usesAi(me)) return null
  if (!open) {
    return (
      <Button variant="link" size="xs" className="px-0" onClick={() => setOpen(true)}>
        {t('agents.sources.show')}
      </Button>
    )
  }
  if (events.isPending) {
    return <p className="text-xs text-muted-foreground">{t('states.loading')}</p>
  }
  if (events.isError) {
    return <p className="text-xs text-destructive">{errorMessage(t, events.error)}</p>
  }
  const { sources, hidden } = sourcesOf(events.data.items)
  return (
    <div className="mt-1 text-xs">
      {sources.length === 0 && hidden === 0 ? (
        <p className="text-muted-foreground">{t('agents.sources.none')}</p>
      ) : (
        <>
          <p className="font-medium text-muted-foreground">{t('agents.sources.title')}</p>
          <ul className="flex flex-col gap-0.5">
            {sources.map((source) => (
              <li key={source.kind === 'page' ? source.id : source.key}>
                <SourceLink source={source} />
              </li>
            ))}
            {hidden > 0 && (
              <li className="text-muted-foreground">
                {t('agents.sources.hidden', { count: hidden })}
              </li>
            )}
          </ul>
        </>
      )}
      <RunLink runId={runId} className="mt-1" />
    </div>
  )
}

function SourceLink({ source }: { source: Source }) {
  const { t } = useTranslation()
  const page = useQuery({
    ...pageQuery(source.kind === 'page' ? source.id : ''),
    enabled: source.kind === 'page',
  })
  if (source.kind === 'ticket') {
    const number = keyNumber(source.key)
    return number ? (
      <Link to="/tickets/$number" params={{ number: String(number) }} className="underline">
        {source.key}
      </Link>
    ) : (
      <span>{source.key}</span>
    )
  }
  if (!page.data) return <span className="text-muted-foreground">{t('agents.sources.page')}</span>
  return (
    <Link
      to="/spaces/$spaceId/p/$"
      params={{ spaceId: page.data.space_id, _splat: page.data.path }}
      className="underline"
    >
      {page.data.title}
    </Link>
  )
}
