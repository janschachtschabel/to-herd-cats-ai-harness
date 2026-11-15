import { useTranslation } from 'react-i18next'
import { useMe } from '@/features/auth/queries'
import { ErrorState, LoadingState } from '@/features/shared/states'
import { usesAi } from '../display'
import { useMyUsage } from '../usageQueries'
import { formatCost } from './period'

/** In the profile: my model and my usage of the last 30 days; nothing at all for
 *  people without `ai.use`. */
export function MyUsage() {
  const { t, i18n } = useTranslation()
  const me = useMe()
  const enabled = usesAi(me)
  const usage = useMyUsage(enabled)
  if (!enabled) return null
  const number = (n: number) => n.toLocaleString(i18n.language)
  return (
    <section aria-labelledby="my-ai-heading" className="mt-8 flex flex-col gap-2 border-t pt-6">
      <h2 id="my-ai-heading" className="font-semibold">
        {t('ai.mine.title')}
      </h2>
      {me?.ai_model && (
        <p className="text-sm text-muted-foreground">
          {t('ai.mine.model', { model: me.ai_model })}
        </p>
      )}
      {usage.isPending ? (
        <LoadingState rows={1} />
      ) : usage.isError ? (
        <ErrorState error={usage.error} onRetry={() => void usage.refetch()} />
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-muted-foreground">{t('ai.usage.calls')}</dt>
              <dd className="font-medium">{number(usage.data.calls)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t('ai.usage.tokensIn')}</dt>
              <dd className="font-medium">{number(usage.data.tokens_in)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t('ai.usage.tokensOut')}</dt>
              <dd className="font-medium">{number(usage.data.tokens_out)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{t('ai.usage.cost')}</dt>
              <dd className="font-medium">
                {formatCost(usage.data.cost, i18n.language) ?? t('ai.usage.noPrice')}
              </dd>
            </div>
          </dl>
          <p className="text-xs text-muted-foreground">
            {t('ai.mine.period', { from: usage.data.first_day, to: usage.data.last_day })}
          </p>
        </>
      )}
    </section>
  )
}
