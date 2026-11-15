import { useId, useState, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import { SaveError } from '@/features/shared/forms'
import type { Schemas } from '@/lib/api'
import { mcpSettingsQuery, useSaveMcpSettings, type McpSettings } from './queries'

const LOCATIONS: readonly Schemas['DataLocation'][] = ['external', 'eu', 'local']

/** The organisation's MCP switch (who holds `mcp.use`) and what an MCP client counts as
 *  for the spaces' AI policy. Saves at the read version; after a 409 the fresh version
 *  is loaded and the choice made is kept. */
export function McpSettingsForm({ settings }: { settings: McpSettings }) {
  const { t } = useTranslation()
  const id = useId()
  const queryClient = useQueryClient()
  const save = useSaveMcpSettings()
  const [enabled, setEnabled] = useState(settings.enabled)
  const [location, setLocation] = useState(settings.data_location)
  const changed = enabled !== settings.enabled || location !== settings.data_location

  const submit = (event: FormEvent) => {
    event.preventDefault()
    save.mutate({ enabled, data_location: location, version: settings.version })
  }
  const reload = async () => {
    await queryClient.fetchQuery({ ...mcpSettingsQuery, staleTime: 0 })
    save.reset()
  }

  return (
    <form
      onSubmit={submit}
      aria-labelledby={`${id}-title`}
      className="flex flex-col gap-4 rounded-lg border p-4"
    >
      <div>
        <h2 id={`${id}-title`} className="text-base font-semibold">
          {t('tokens.admin.settings.title')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('tokens.admin.settings.hint')}</p>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-0.5 size-4 accent-primary"
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
        />
        <span>
          <span className="font-medium">{t('tokens.admin.settings.enabled')}</span>
          <span className="block text-xs text-muted-foreground">
            {t('tokens.admin.settings.enabledHint')}
          </span>
        </span>
      </label>
      <p role="status" className="text-xs text-muted-foreground">
        {settings.enabled ? t('tokens.admin.settings.on') : t('tokens.admin.settings.off')}
      </p>
      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${id}-location`} className="text-sm font-medium">
          {t('tokens.admin.settings.location')}
        </label>
        <NativeSelect
          id={`${id}-location`}
          className="max-w-xs"
          aria-describedby={`${id}-location-hint`}
          value={location}
          onChange={(event) => setLocation(event.target.value as Schemas['DataLocation'])}
        >
          {LOCATIONS.map((value) => (
            <option key={value} value={value}>
              {t(`ai.locations.${value}`)}
            </option>
          ))}
        </NativeSelect>
        <p id={`${id}-location-hint`} className="text-xs text-muted-foreground">
          {t('tokens.admin.settings.locationHint')}
        </p>
      </div>
      <SaveError error={save.error} onReload={() => void reload()} />
      <div>
        <Button type="submit" size="sm" disabled={save.isPending || !changed}>
          {t('actions.save')}
        </Button>
      </div>
    </form>
  )
}
