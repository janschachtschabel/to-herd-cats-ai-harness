import { ArrowDownUp, Download, Upload } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useWiki } from '../WikiContext'
import { ImportDialog } from './ImportDialog'
import { spaceExportUrl } from './queries'

/** Export the space as a ZIP of Markdown (everyone who reads it); import (space.manage). */
export function SpaceTransferMenu() {
  const { t } = useTranslation()
  const { space, abilities } = useWiki()
  const [importing, setImporting] = useState(false)
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline">
            <ArrowDownUp aria-hidden />
            {t('wiki.transfer.menu')}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem asChild>
            <a href={spaceExportUrl(space.id)} download>
              <Download aria-hidden />
              {t('wiki.transfer.export')}
            </a>
          </DropdownMenuItem>
          {abilities.manage && (
            <DropdownMenuItem onSelect={() => setImporting(true)}>
              <Upload aria-hidden />
              {t('wiki.transfer.import')}
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      {abilities.manage && <ImportDialog open={importing} onOpenChange={setImporting} />}
    </>
  )
}
