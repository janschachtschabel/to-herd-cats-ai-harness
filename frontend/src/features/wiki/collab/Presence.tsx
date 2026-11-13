import { useTranslation } from 'react-i18next'
import type { Peer } from './liveSession'

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

/** Who else is in the document, by name and colour. */
export function Presence({ peers }: { peers: Peer[] }) {
  const { t } = useTranslation()
  if (peers.length === 0)
    return <p className="text-xs text-muted-foreground">{t('wiki.live.alone')}</p>
  return (
    <ul aria-label={t('wiki.live.present')} className="flex items-center -space-x-1.5">
      {peers.map((peer) => (
        <li
          key={peer.clientId}
          title={peer.name}
          className="flex size-7 items-center justify-center rounded-full border-2 border-background text-[11px] font-semibold text-white"
          style={{ backgroundColor: peer.color }}
        >
          <span aria-hidden>{initials(peer.name)}</span>
          <span className="sr-only">{peer.name}</span>
        </li>
      ))}
    </ul>
  )
}
