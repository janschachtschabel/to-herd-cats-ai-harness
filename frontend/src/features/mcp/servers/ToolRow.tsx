import { useQueryClient } from '@tanstack/react-query'
import { Ban, Check } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { SaveError } from '@/features/shared/forms'
import { CLASSIFICATIONS, toolView, type Classification, type Tool } from '../display'
import { mcpKeys } from '../keys'
import { useChangeTool } from '../serverQueries'
import { ToolFacts, ToolStateBadge } from './ToolFacts'

/** One tool of a server: its state, its description and schema as the server sent
 *  them (untrusted text, shown as text), its classification (read or write, with the
 *  catalogue's suggestion), and approve or block. A tool the server no longer lists
 *  cannot be approved, nor one whose schema cannot be offered to a model; a changed one
 *  needs a new approval. Loosening to "read" a tool
 *  the server does not mark read-only is asked once more. */
export function ToolRow({ serverId, tool }: { serverId: string; tool: Tool }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const change = useChangeTool(serverId, tool.id)
  const [loosening, setLoosening] = useState(false)
  const view = toolView(tool)
  const reload = () => {
    change.reset()
    void queryClient.invalidateQueries({ queryKey: mcpKeys.tools(serverId) })
  }

  const classify = (classification: Classification, confirmLoosen = false) =>
    change.mutate(
      {
        action: 'classify',
        body: { classification, confirm_loosen: confirmLoosen, version: tool.version },
      },
      { onSuccess: () => setLoosening(false) },
    )

  const onClassify = (next: Classification) => {
    if (next === tool.classification) return
    if (next === 'read' && !tool.read_only_hint) setLoosening(true)
    else classify(next)
  }

  return (
    <article
      aria-label={tool.name}
      data-tool-state={view}
      className="flex flex-col gap-2 rounded-lg border p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="font-mono text-sm font-semibold break-all">{tool.name}</h3>
        <ToolStateBadge view={view} />
      </div>
      <ToolFacts tool={tool} view={view} />
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          {t('mcp.tools.classification')}
          <NativeSelect
            aria-label={t('mcp.tools.classifyFor', { name: tool.name })}
            className="min-w-40"
            value={tool.classification}
            disabled={change.isPending}
            onChange={(event) => onClassify(event.target.value as Classification)}
          >
            {CLASSIFICATIONS.map((value) => (
              <option key={value} value={value}>
                {t(`mcp.tools.classes.${value}`)}
              </option>
            ))}
          </NativeSelect>
        </label>
        <div className="flex flex-wrap gap-2">
          {view !== 'approved' && view !== 'missing' && !tool.schema_problem && (
            <Button
              size="sm"
              disabled={change.isPending}
              onClick={() => change.mutate({ action: 'approve', version: tool.version })}
              aria-label={t('mcp.tools.approveNamed', { name: tool.name })}
            >
              <Check aria-hidden />
              {view === 'changed' ? t('mcp.tools.approveAgain') : t('mcp.tools.approve')}
            </Button>
          )}
          {view !== 'blocked' && (
            <Button
              size="sm"
              variant="outline"
              disabled={change.isPending}
              onClick={() => change.mutate({ action: 'block', version: tool.version })}
              aria-label={t('mcp.tools.blockNamed', { name: tool.name })}
            >
              <Ban aria-hidden />
              {t('mcp.tools.block')}
            </Button>
          )}
        </div>
      </div>
      <SaveError error={change.error} onReload={reload} />
      <ConfirmDialog
        open={loosening}
        title={t('mcp.tools.loosenTitle')}
        text={t('mcp.tools.loosenText', { name: tool.name })}
        confirmLabel={t('mcp.tools.loosenConfirm')}
        pending={change.isPending}
        error={change.error}
        onOpenChange={setLoosening}
        onConfirm={() => classify('read', true)}
      />
    </article>
  )
}
