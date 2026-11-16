import { screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { reload, resetMaintenance } from '@/features/shared/maintenance'
import type { Permission } from '@/lib/api'
import { ADMIN_PERMISSIONS, apiError, makeMe, mockApi, page } from '@/test/api'
import { renderApp } from '@/test/render'
import type { Archive, ArchiveCheck, ArchiveFigures, BackupRun } from './queries'

const OWNER: Permission[] = [...ADMIN_PERMISSIONS, 'backup.manage']
const NAME = 'herd-20261116T080000Z-1.0.0.tar'

const shell = (permissions: Permission[]) => ({
  'GET /api/auth/me': makeMe(permissions),
  'GET /api/spaces': page([]),
})

function makeRun(overrides: Partial<BackupRun> = {}): BackupRun {
  return {
    id: '00000000-0000-7000-8000-0000000b0001',
    trigger: 'schedule',
    state: 'ok',
    started_at: '2026-11-16T08:00:00Z',
    finished_at: '2026-11-16T08:01:00Z',
    archive: NAME,
    archive_sha256: 'ab'.repeat(32),
    bytes: 4096,
    error_code: null,
    offsite_state: 'off',
    ...overrides,
  }
}

const archive: Archive = {
  name: NAME,
  bytes: 4096,
  created_at: '2026-11-16T08:00:00Z',
  uploaded: false,
}

const figures: ArchiveFigures = {
  app_version: '1.0.0',
  alembic_revision: 'a3c5e7f9b2d4',
  server_major: 17,
  tools_major: 17,
  storage: 'local',
  tables: 80,
  rows: 1200,
  files: 3,
  file_bytes: 2048,
}

function makeCheck(overrides: Partial<ArchiveCheck> = {}): ArchiveCheck {
  return {
    archive_name: NAME,
    created_at: '2026-11-16T08:00:00Z',
    archive: figures,
    installation: figures,
    key: 'match',
    problems: [],
    warnings: [],
    can_replace: true,
    ...overrides,
  }
}

const backupRoutes = (runs: BackupRun[] = [makeRun()]) => ({
  ...shell(OWNER),
  'GET /api/backups': () => page(runs),
  'GET /api/backups/archives': page([archive]),
  'GET /api/backups/restore': { attempt: null },
})

// Before each test: resetting after one would show its app again before cleanup.
beforeEach(() => resetMaintenance())

describe('backup administration', () => {
  test('an admin who is not an owner: no menu entry, not found, no backup request', async () => {
    const api = mockApi(shell(ADMIN_PERMISSIONS))
    await renderApp('/admin/backup')
    expect(await screen.findByRole('heading', { name: 'Seite nicht gefunden' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Sicherung' })).not.toBeInTheDocument()
    expect(api.calls.filter((c) => c.path.startsWith('/api/backups'))).toEqual([])
  })

  test('the owner sees backups and archives, starts one and is pointed to the space export', async () => {
    const runs = [makeRun()]
    const api = mockApi({
      ...backupRoutes(runs),
      'POST /api/backups': () => {
        const requested = makeRun({
          id: '00000000-0000-7000-8000-0000000b0002',
          trigger: 'admin',
          state: 'running',
          finished_at: null,
          archive: null,
          archive_sha256: null,
          bytes: null,
          started_at: '2026-11-16T09:00:00Z',
        })
        runs.unshift(requested)
        return { status: 202, body: requested }
      },
    })
    const { user } = await renderApp('/admin/backup')
    expect(await screen.findByRole('heading', { name: 'Sicherung', level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sicherung' })).toBeInTheDocument()
    expect(await screen.findByText('gelungen')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: `${NAME} herunterladen` })).toHaveAttribute(
      'href',
      `/api/backups/archives/${NAME}`,
    )
    expect(screen.getByText(/Bereich exportieren \(ZIP\)/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Jetzt sichern' }))
    expect(await screen.findByText('wartet auf den Worker')).toBeInTheDocument()
    expect(api.find('POST', '/api/backups')).toHaveLength(1)
  })

  test('a key that does not fit blocks restoring, and says so', async () => {
    const api = mockApi({
      ...backupRoutes(),
      'POST /api/backups/archives/:name/check': makeCheck({
        key: 'mismatch',
        problems: ['restore.secret_key_mismatch'],
        can_replace: false,
      }),
    })
    const { user } = await renderApp('/admin/backup')
    await user.click(await screen.findByRole('button', { name: `${NAME} prüfen` }))
    expect(
      await screen.findByText(/Der Schlüssel dieser Installation passt nicht zum Archiv/),
    ).toBeInTheDocument()
    expect(screen.getByText('passt nicht')).toBeInTheDocument()
    expect(
      screen.getByText('Der Schlüssel (HERD_SECRET_KEY) passt nicht zum Archiv.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Einspielen …' })).toBeDisabled()
    expect(api.find('POST', `/api/backups/archives/${NAME}/check`)).toHaveLength(1)
  })

  test('a manipulated archive shows the checksum problem', async () => {
    mockApi({
      ...backupRoutes(),
      'POST /api/backups/archives/:name/check': makeCheck({
        archive: null,
        installation: null,
        key: null,
        problems: ['archive.checksum'],
        can_replace: false,
      }),
    })
    const { user } = await renderApp('/admin/backup')
    await user.click(await screen.findByRole('button', { name: `${NAME} prüfen` }))
    expect(
      await screen.findByText(/Das Archiv wurde nach dem Sichern verändert/),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Einspielen …' })).toBeDisabled()
  })

  test('replacing takes the organisation name exactly, then shows the maintenance page', async () => {
    let maintenance = false
    const assign = vi.spyOn(reload, 'to').mockImplementation(() => {})
    const api = mockApi({
      ...backupRoutes(),
      'POST /api/backups/archives/:name/check': makeCheck(),
      'POST /api/backups/archives/:name/replace': (call) => {
        maintenance = true
        return { status: 202, body: { archive_name: NAME, ...(call.body as object) } }
      },
      'GET /api/maintenance': () => ({
        active: maintenance,
        reason: maintenance ? 'restore' : null,
        started_at: maintenance ? '2026-11-16T09:00:00Z' : null,
      }),
    })
    const { user } = await renderApp('/admin/backup')
    await user.click(await screen.findByRole('button', { name: `${NAME} prüfen` }))
    await user.click(await screen.findByRole('button', { name: 'Einspielen …' }))
    const dialog = await screen.findByRole('dialog')
    const field = within(dialog).getByLabelText(/Beispiel GmbH/)
    const submit = within(dialog).getByRole('button', { name: 'Ersetzen' })
    await user.type(field, 'beispiel gmbh')
    expect(submit).toBeDisabled()
    await user.clear(field)
    await user.type(field, 'Beispiel GmbH')
    await user.click(submit)

    expect(
      await screen.findByRole('heading', { name: 'Wartung' }, { timeout: 5000 }),
    ).toBeInTheDocument()
    expect(api.find('POST', `/api/backups/archives/${NAME}/replace`)[0]?.body).toEqual({
      confirm: 'Beispiel GmbH',
    })
    expect(assign).not.toHaveBeenCalled()
    assign.mockRestore()
  })

  test('any request answered 503 maintenance.active shows the maintenance page; its end reloads', async () => {
    let active = true
    const assign = vi.spyOn(reload, 'to').mockImplementation(() => {})
    mockApi({
      ...shell(OWNER),
      'GET /api/backups': apiError(503, 'maintenance.active'),
      'GET /api/backups/archives': apiError(503, 'maintenance.active'),
      'GET /api/backups/restore': apiError(503, 'maintenance.active'),
      'GET /api/maintenance': () => ({
        active,
        reason: active ? 'restore' : null,
        started_at: null,
      }),
    })
    await renderApp('/admin/backup')
    expect(await screen.findByRole('heading', { name: 'Wartung' })).toBeInTheDocument()
    expect(assign).not.toHaveBeenCalled()
    active = false
    await waitFor(() => expect(assign).toHaveBeenCalledWith('/'), { timeout: 5000 })
    assign.mockRestore()
  })
})
