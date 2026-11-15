import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { EmptyState, ErrorState, LoadingState, LoadMore } from '@/features/shared/states'
import { toolNeedsAttention, toolView, type ToolView } from '../display'
import { useServerTools } from '../serverQueries'
import { ToolRow } from './ToolRow'

const COUNTED: readonly ToolView[] = ['new', 'changed', 'approved', 'blocked', 'missing']

/** A server's tools, each approved one by one. Open ones (new, changed) can be shown
 *  alone; the counts per state are named above the list. */
export function ToolList({ serverId }: { serverId: string }) {
  const { t } = useTranslation()
  const tools = useServerTools(serverId)
  const [openOnly, setOpenOnly] = useState(false)
  if (tools.isPending) return <LoadingState rows={3} />
  if (tools.isError) return <ErrorState error={tools.error} onRetry={() => void tools.refetch()} />
  if (tools.items.length === 0) return <EmptyState text={t('mcp.tools.empty')} />
  const counts = COUNTED.map((view) => ({
    view,
    count: tools.items.filter((tool) => toolView(tool) === view).length,
  })).filter(({ count }) => count > 0)
  const shown = openOnly ? tools.items.filter(toolNeedsAttention) : tools.items
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          {counts.map(({ view, count }) => t(`mcp.tools.counts.${view}`, { count })).join(' · ')}
        </p>
        <div role="group" aria-label={t('mcp.tools.filterLabel')} className="flex gap-1">
          <Button
            size="xs"
            variant={openOnly ? 'ghost' : 'secondary'}
            aria-pressed={!openOnly}
            onClick={() => setOpenOnly(false)}
          >
            {t('mcp.tools.filterAll')}
          </Button>
          <Button
            size="xs"
            variant={openOnly ? 'secondary' : 'ghost'}
            aria-pressed={openOnly}
            onClick={() => setOpenOnly(true)}
          >
            {t('mcp.tools.filterOpen')}
          </Button>
        </div>
      </div>
      {shown.length === 0 ? (
        <EmptyState text={t('mcp.tools.noneOpen')} />
      ) : (
        <ul className="flex flex-col gap-3" aria-label={t('mcp.tools.listLabel')}>
          {shown.map((tool) => (
            <li key={tool.id}>
              <ToolRow serverId={serverId} tool={tool} />
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={tools.hasMore} loading={tools.loadingMore} onLoad={tools.loadMore} />
    </div>
  )
}
