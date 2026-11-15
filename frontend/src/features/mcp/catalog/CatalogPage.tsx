import { Download, ExternalLink, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AiAdminTabs } from '@/features/ai/AiAdminTabs'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  LoadMore,
  PageHeader,
} from '@/features/shared/states'
import { useCatalog, useCatalogProblems } from '../catalogQueries'
import { localized, type CatalogEntry } from '../display'
import { InstallDialog } from './InstallDialog'

function EntryCard({ entry, onInstall }: { entry: CatalogEntry; onInstall: () => void }) {
  const { t, i18n } = useTranslation()
  const tools = Object.values(entry.tools ?? {})
  const writes = tools.filter((c) => c === 'write').length
  return (
    <article aria-label={entry.name} className="flex h-full flex-col gap-3 rounded-lg border p-4">
      <div>
        <h2 className="font-semibold">{entry.name}</h2>
        <p className="font-mono text-xs break-all text-muted-foreground">{entry.url}</p>
      </div>
      <p className="text-sm">{localized(entry.description, i18n.language)}</p>
      <span className="flex flex-wrap gap-1.5">
        {entry.connector_scopes.map((scope) => (
          <Badge key={scope} variant="outline">
            {t(`mcp.access.${scope}`)}
          </Badge>
        ))}
        {(entry.auth ?? []).map((a) => (
          <Badge key={a.kind} variant="secondary">
            {t(`mcp.connectors.kinds.${a.kind}`)}
          </Badge>
        ))}
      </span>
      {tools.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {t('mcp.catalog.suggestions', { count: tools.length, writes })}
        </p>
      )}
      {(entry.docs ?? []).length > 0 && (
        <ul className="flex flex-col gap-0.5 text-xs">
          {(entry.docs ?? []).map((url) => (
            <li key={url}>
              <a
                href={url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 break-all underline underline-offset-2"
              >
                <ExternalLink className="size-3 shrink-0" aria-hidden />
                {url}
              </a>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-auto">
        <Button size="sm" onClick={onInstall}>
          <Download aria-hidden />
          {t('mcp.catalog.installNamed', { name: entry.name })}
        </Button>
      </div>
    </article>
  )
}

/** Operator files of the catalogue that could not be read: file, source and where the
 *  error is (never the file's content). Shown only when there are any. */
function Problems() {
  const { t } = useTranslation()
  const problems = useCatalogProblems()
  if (problems.isPending || problems.items.length === 0) {
    return problems.isError ? <ErrorState error={problems.error} /> : null
  }
  return (
    <section
      aria-labelledby="catalog-problems"
      className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100"
    >
      <h2 id="catalog-problems" className="inline-flex items-center gap-1.5 font-semibold">
        <TriangleAlert className="size-4" aria-hidden />
        {t('mcp.catalog.problems.title')}
      </h2>
      <p className="mt-1 text-sm">{t('mcp.catalog.problems.hint')}</p>
      <ul className="mt-2 flex flex-col gap-1 text-sm">
        {problems.items.map((problem) => (
          <li key={`${problem.source}-${problem.file}`}>
            <span className="font-mono font-medium">{problem.file}</span>{' '}
            <span className="text-xs">({t(`mcp.catalog.problems.sources.${problem.source}`)})</span>
            <span className="block font-mono text-xs break-words">{problem.reason}</span>
          </li>
        ))}
      </ul>
      <LoadMore
        hasMore={problems.hasMore}
        loading={problems.loadingMore}
        onLoad={problems.loadMore}
      />
    </section>
  )
}

/** The catalogue (`ai.manage`): templates for external servers, shipped (GitHub,
 *  GitLab) and from the operator's directory. A template only proposes: every tool of
 *  an installed server is still approved one by one. */
export function CatalogPage() {
  const { t } = useTranslation()
  const catalog = useCatalog()
  const [installing, setInstalling] = useState<CatalogEntry | null>(null)
  return (
    <div>
      <PageHeader title={t('ai.title')} description={t('mcp.catalog.description')} />
      <AiAdminTabs />
      <div className="flex flex-col gap-6">
        <Problems />
        {catalog.isPending ? (
          <LoadingState rows={2} />
        ) : catalog.isError ? (
          <ErrorState error={catalog.error} onRetry={() => void catalog.refetch()} />
        ) : catalog.items.length === 0 ? (
          <EmptyState text={t('mcp.catalog.empty')} />
        ) : (
          <ul className="grid gap-3 md:grid-cols-2" aria-label={t('mcp.catalog.listLabel')}>
            {catalog.items.map((entry) => (
              <li key={entry.id}>
                <EntryCard entry={entry} onInstall={() => setInstalling(entry)} />
              </li>
            ))}
          </ul>
        )}
        <LoadMore
          hasMore={catalog.hasMore}
          loading={catalog.loadingMore}
          onLoad={catalog.loadMore}
        />
      </div>
      <InstallDialog entry={installing} onOpenChange={(open) => !open && setInstalling(null)} />
    </div>
  )
}
