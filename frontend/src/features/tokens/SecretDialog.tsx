import { TriangleAlert } from 'lucide-react'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { CopyButton } from './CopyButton'
import { connectSnippets, tokenVariable } from './display'
import type { CreatedToken } from './queries'

/** A new token's clear text, shown this once with a copy button and a clear warning,
 *  then how to connect Claude Code or Codex to this installation's `/mcp`. Closing it
 *  drops the clear text: nothing keeps it. */
export function SecretDialog({
  token,
  forAgent = false,
  onClose,
}: {
  token: CreatedToken | null
  forAgent?: boolean
  onClose: () => void
}) {
  const { t } = useTranslation()
  const secretId = useId()
  const snippets = connectSnippets(window.location.origin, forAgent)
  const variable = tokenVariable(forAgent)
  return (
    <Dialog open={token !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t('tokens.secret.title', { name: token?.name ?? '' })}</DialogTitle>
          <DialogDescription>{t('tokens.secret.description')}</DialogDescription>
        </DialogHeader>
        {token && (
          <div className="flex min-w-0 flex-col gap-4">
            <Alert className="border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100">
              <TriangleAlert aria-hidden />
              <AlertDescription className="text-current">
                {t('tokens.secret.warning')}
              </AlertDescription>
            </Alert>
            <div className="flex flex-col gap-1.5">
              <label htmlFor={secretId} className="text-sm font-medium">
                {t('tokens.secret.label')}
              </label>
              <div className="flex flex-wrap gap-2">
                <input
                  id={secretId}
                  readOnly
                  value={token.secret}
                  onFocus={(event) => event.currentTarget.select()}
                  className="min-w-0 flex-1 rounded-md border bg-muted px-3 py-2 font-mono text-sm"
                />
                <CopyButton text={token.secret} label={t('tokens.secret.copy')} />
              </div>
            </div>
            <section aria-labelledby={`${secretId}-connect`} className="flex flex-col gap-3">
              <h3 id={`${secretId}-connect`} className="font-semibold">
                {t('tokens.connect.title')}
              </h3>
              <p className="text-sm text-muted-foreground">
                {t('tokens.connect.variable', { variable })}
              </p>
              <Snippet title={t('tokens.connect.claude')} text={snippets.claude} />
              <Snippet title={t('tokens.connect.codex')} text={snippets.codex} />
              {forAgent && (
                <p className="text-sm text-muted-foreground">{t('tokens.connect.agentTask')}</p>
              )}
            </section>
          </div>
        )}
        <DialogFooter>
          <Button onClick={onClose}>{t('tokens.secret.done')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function Snippet({ title, text }: { title: string; text: string }) {
  const { t } = useTranslation()
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{title}</span>
        <CopyButton text={text} label={t('tokens.connect.copy', { what: title })} />
      </div>
      <pre className="overflow-x-auto rounded-md border bg-muted p-3 font-mono text-xs leading-relaxed">
        <code>{text}</code>
      </pre>
    </div>
  )
}
