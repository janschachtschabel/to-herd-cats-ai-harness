import { useNavigate } from '@tanstack/react-router'
import { Pencil, PlugZap, RefreshCw, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/features/shared/ConfirmDialog'
import { SaveError } from '@/features/shared/forms'
import type { Server } from '../display'
import { useDeleteServer, useRefreshTools, useTestServer, useUpdateServer } from '../serverQueries'
import { RefreshSummary, TestResult } from './RemoteResult'
import { ServerDialog } from './ServerDialog'

/** What one can do with a server: test the connection, read its tools again, switch it
 *  on or off, change or delete it. Each answer is shown in words below. */
export function ServerActions({ server }: { server: Server }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const test = useTestServer(server.id)
  const refresh = useRefreshTools(server.id)
  const toggle = useUpdateServer(server.id)
  const remove = useDeleteServer()
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const failure = test.error ?? refresh.error ?? toggle.error

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" disabled={test.isPending} onClick={() => test.mutate()}>
          <PlugZap aria-hidden />
          {test.isPending ? t('mcp.servers.testing') : t('mcp.servers.test')}
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={refresh.isPending}
          onClick={() => refresh.mutate()}
        >
          <RefreshCw aria-hidden />
          {refresh.isPending ? t('mcp.servers.refreshing') : t('mcp.servers.refresh')}
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={toggle.isPending}
          onClick={() => toggle.mutate({ enabled: !server.enabled, version: server.version })}
        >
          {server.enabled ? t('mcp.servers.disable') : t('mcp.servers.enable')}
        </Button>
        <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
          <Pencil aria-hidden />
          {t('actions.edit')}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label={t('mcp.servers.deleteNamed', { name: server.name })}
          onClick={() => setConfirming(true)}
        >
          <Trash2 aria-hidden />
        </Button>
      </div>
      {test.data && (
        <TestResult
          status={test.data.status}
          tools={test.data.tools}
          durationMs={test.data.duration_ms}
        />
      )}
      {refresh.data && <RefreshSummary result={refresh.data} />}
      {failure ? <SaveError error={failure} /> : null}
      <ServerDialog key={server.version} open={editing} server={server} onOpenChange={setEditing} />
      <ConfirmDialog
        open={confirming}
        title={t('mcp.servers.deleteTitle')}
        text={t('mcp.servers.deleteText', { name: server.name })}
        confirmLabel={t('actions.delete')}
        destructive
        pending={remove.isPending}
        error={remove.error}
        onOpenChange={setConfirming}
        onConfirm={() =>
          remove.mutate(
            { id: server.id, version: server.version },
            { onSuccess: () => void navigate({ to: '/admin/ai/mcp-servers' }) },
          )
        }
      />
    </div>
  )
}
