import { useTranslation } from 'react-i18next'
import { AiAdminTabs } from '@/features/ai/AiAdminTabs'
import { ErrorState, LoadingState, PageHeader } from '@/features/shared/states'
import { useSpaces } from '@/features/spaces/queries'
import { McpSettingsForm } from './McpSettingsForm'
import { useMcpSettings, useOrgTokens, type AdminToken } from './queries'
import { TokenList } from './TokenList'

const ORG = { kind: 'org' } as const

/** MCP in the AI administration (`ai.manage`): the switch and data location, and every
 *  token of the organisation (metadata and whose it is; revoke, calls). */
export function McpAdminPage() {
  const { t } = useTranslation()
  const settings = useMcpSettings()
  const tokens = useOrgTokens()
  const spaces = useSpaces()
  const names = new Map(spaces.items.map((space) => [space.id, space.name]))
  const ownerOf = (token: AdminToken) =>
    token.agent
      ? t('tokens.admin.ownerAgent', { agent: token.agent.name, name: token.user.name })
      : t('tokens.admin.ownerPerson', { name: token.user.name })
  return (
    <div>
      <PageHeader title={t('ai.title')} description={t('tokens.admin.description')} />
      <AiAdminTabs />
      <div className="flex max-w-3xl flex-col gap-8">
        {settings.isPending ? (
          <LoadingState rows={2} />
        ) : settings.isError ? (
          <ErrorState error={settings.error} onRetry={() => void settings.refetch()} />
        ) : (
          <McpSettingsForm settings={settings.data} />
        )}
        <section aria-labelledby="mcp-tokens" className="flex flex-col gap-3">
          <div>
            <h2 id="mcp-tokens" className="text-base font-semibold">
              {t('tokens.admin.tokensTitle')}
            </h2>
            <p className="text-sm text-muted-foreground">{t('tokens.admin.tokensHint')}</p>
          </div>
          <TokenList
            tokens={tokens}
            owner={ORG}
            spaceNames={names}
            emptyText={t('tokens.admin.empty')}
            label={t('tokens.admin.tokensTitle')}
            ownerOf={ownerOf}
          />
        </section>
      </div>
    </div>
  )
}
