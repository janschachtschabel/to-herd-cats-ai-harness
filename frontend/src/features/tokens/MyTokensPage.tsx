import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/features/shared/states'
import { useSpaces } from '@/features/spaces/queries'
import { CreateTokenDialog } from './CreateTokenDialog'
import { useMyTokens, type CreatedToken } from './queries'
import { SecretDialog } from './SecretDialog'
import { TokenList } from './TokenList'

const MINE = { kind: 'mine' } as const

/** My access tokens for AI clients over MCP (`mcp.use`): list, create (the clear text
 *  once, with how to connect), revoke, recent calls. */
export function MyTokensPage() {
  const { t } = useTranslation()
  const tokens = useMyTokens()
  const spaces = useSpaces()
  const [creating, setCreating] = useState(false)
  const [shown, setShown] = useState<CreatedToken | null>(null)
  const names = new Map(spaces.items.map((space) => [space.id, space.name]))
  return (
    <div className="max-w-3xl">
      <PageHeader
        title={t('tokens.title')}
        description={t('tokens.description')}
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden />
            {t('tokens.create.open')}
          </Button>
        }
      />
      <TokenList
        tokens={tokens}
        owner={MINE}
        spaceNames={names}
        emptyText={t('tokens.empty')}
        label={t('tokens.listLabel')}
      />
      <CreateTokenDialog
        open={creating}
        spaces={spaces}
        onOpenChange={setCreating}
        onCreated={(token) => {
          setCreating(false)
          setShown(token)
        }}
      />
      <SecretDialog token={shown} onClose={() => setShown(null)} />
    </div>
  )
}
