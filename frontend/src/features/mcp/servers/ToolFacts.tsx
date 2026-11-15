import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { changedParts, type Tool, type ToolView } from '../display'

const STATE_TONES: Record<ToolView, string> = {
  new: 'border-violet-300 bg-violet-50 text-violet-900 dark:border-violet-500/40 dark:bg-violet-500/15 dark:text-violet-100',
  approved:
    'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-500/40 dark:bg-emerald-500/15 dark:text-emerald-100',
  blocked: 'border-border bg-muted text-muted-foreground',
  changed:
    'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/15 dark:text-amber-100',
  missing: 'border-dashed border-border text-muted-foreground',
}

/** A tool's state as a badge; its words carry the meaning. */
export function ToolStateBadge({ view }: { view: ToolView }) {
  const { t } = useTranslation()
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium',
        STATE_TONES[view],
      )}
    >
      {t(`mcp.tools.states.${view}`)}
    </span>
  )
}

const short = (fingerprint: string) => fingerprint.slice(0, 12)

/** Which parts changed since the approval, and the approved version, folded (or that
 *  it was not kept: an approval from before it was). */
function ChangedSince({ tool }: { tool: Tool }) {
  const { t } = useTranslation()
  const parts = changedParts(tool)
  if (parts === null) return <p className="mt-1 text-xs">{t('mcp.tools.approvedNotKept')}</p>
  return (
    <>
      {parts.length > 0 && (
        <p className="mt-1 text-xs font-medium">
          {t('mcp.tools.changedParts', {
            parts: parts.map((part) => t(`mcp.tools.parts.${part}`)).join(', '),
          })}
        </p>
      )}
      <details className="mt-1 text-xs">
        <summary className="cursor-pointer font-medium select-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none">
          {t('mcp.tools.approvedVersion')}
        </summary>
        <p className="mt-1 break-words whitespace-pre-wrap">{tool.approved_description}</p>
        <pre className="mt-1 max-h-72 overflow-auto font-mono break-words whitespace-pre-wrap">
          {JSON.stringify(tool.approved_input_schema, null, 2)}
        </pre>
      </details>
    </>
  )
}

/** What the admin needs to decide: why a changed or missing tool is held back (with
 *  both fingerprints when the API has them, what changed and the approved version), why a schema cannot be offered to a model
 *  (then the tool cannot be approved), what the server and the catalogue say
 *  about reading or writing, what the classification means for agents, and the
 *  server's description and input schema, folded. */
export function ToolFacts({ tool, view }: { tool: Tool; view: ToolView }) {
  const { t } = useTranslation()
  const suggested = tool.suggested_classification
  return (
    <>
      {view === 'changed' && (
        <div
          role="note"
          className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100"
        >
          <p>{t('mcp.tools.changedNote')}</p>
          {tool.approved_fingerprint && (
            <p className="mt-1 font-mono text-xs">
              {t('mcp.tools.fingerprints', {
                approved: short(tool.approved_fingerprint),
                now: short(tool.fingerprint),
              })}
            </p>
          )}
          <ChangedSince tool={tool} />
        </div>
      )}
      {view === 'missing' && (
        <p role="note" className="text-sm text-muted-foreground">
          {t('mcp.tools.missingNote')}
        </p>
      )}
      {tool.schema_problem && (
        <p
          role="note"
          className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100"
        >
          {t(`mcp.tools.schemaProblem.${tool.schema_problem}`)}
        </p>
      )}
      {tool.description && (
        <p className="line-clamp-2 text-sm break-words text-muted-foreground">{tool.description}</p>
      )}
      <ul className="flex flex-col gap-0.5 text-xs text-muted-foreground">
        <li>{tool.read_only_hint ? t('mcp.tools.hintReadOnly') : t('mcp.tools.hintNone')}</li>
        {suggested && (
          <li>
            {t('mcp.tools.suggested', { classification: t(`mcp.tools.classes.${suggested}`) })}
            {suggested !== tool.classification && (
              <span className="font-medium text-amber-800 dark:text-amber-300">
                {' '}
                {t('mcp.tools.suggestedDiffers')}
              </span>
            )}
          </li>
        )}
        <li>{t(`mcp.tools.means.${tool.classification}`)}</li>
      </ul>
      <details className="rounded-md border bg-muted/30 text-xs">
        <summary className="cursor-pointer px-2 py-1 font-medium select-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none">
          {t('mcp.tools.details')}
        </summary>
        <div className="flex flex-col gap-2 px-2 pb-2">
          <p className="break-words whitespace-pre-wrap">{tool.description}</p>
          <pre className="max-h-72 overflow-auto font-mono break-words whitespace-pre-wrap">
            {JSON.stringify(tool.input_schema, null, 2)}
          </pre>
        </div>
      </details>
    </>
  )
}
