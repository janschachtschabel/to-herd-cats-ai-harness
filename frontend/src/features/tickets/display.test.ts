import { describe, expect, test } from 'vitest'
import { systemText } from '@/features/messaging/display'
import type { SystemEntry } from '@/lib/api'
import i18n from '@/lib/i18n'

const t = i18n.t.bind(i18n)

function entry(key: string, old: SystemEntry['old'] = null, next: SystemEntry['new'] = null) {
  return { key, actor: { id: 'jan', name: 'Jan Jansen' }, number: null, old, new: next }
}

describe('ticket timeline wording', () => {
  test('ids come named, enumeration values and days are worded here', () => {
    expect(
      systemText(
        t,
        entry(
          'ticket.priority_changed',
          { value: 'normal', name: null },
          { value: 'urgent', name: null },
        ),
      ),
    ).toBe('Jan Jansen hat die Priorität von Normal auf Dringend geändert.')
    expect(systemText(t, entry('ticket.assigned', null, { value: 'x', name: 'Lea Löwe' }))).toBe(
      'Jan Jansen hat das Ticket Lea Löwe zugewiesen.',
    )
    expect(systemText(t, entry('ticket.parent_changed', { value: 'p', name: 'HC-3' }))).toBe(
      'Jan Jansen hat das Ticket aus HC-3 herausgenommen.',
    )
    expect(systemText(t, entry('ticket.due_changed', { value: '2026-11-20', name: null }))).toBe(
      'Jan Jansen hat die Fälligkeit entfernt.',
    )
  })

  test('what the reader may not see, or what is gone, is not named', () => {
    expect(systemText(t, entry('ticket.page_linked'))).toBe('Jan Jansen hat eine Seite verknüpft.')
    expect(
      systemText(
        t,
        entry('ticket.status_changed', { value: 's', name: null }, { value: 't', name: 'Neu' }),
      ),
    ).toBe('Jan Jansen hat den Status von einem gelöschten Status auf Neu gesetzt.')
    expect(systemText(t, { ...entry('ticket.renamed_somehow'), actor: null })).toBe(
      'Jemand hat das Ticket geändert.',
    )
  })

  test('a change of sprint names both sprints, or the backlog', () => {
    const s11 = { value: 's11', name: 'Sprint 11' }
    const s12 = { value: 's12', name: 'Sprint 12' }
    expect(systemText(t, entry('ticket.sprint_changed', null, s12))).toBe(
      'Jan Jansen hat das Ticket in Sprint 12 gelegt.',
    )
    expect(systemText(t, entry('ticket.sprint_changed', s11, s12))).toBe(
      'Jan Jansen hat das Ticket von Sprint 11 nach Sprint 12 verschoben.',
    )
    expect(systemText(t, entry('ticket.sprint_changed', s11, null))).toBe(
      'Jan Jansen hat das Ticket aus Sprint 11 in den Vorrat gelegt.',
    )
    expect(systemText(t, entry('ticket.sprint_changed', null, { value: 's13', name: null }))).toBe(
      'Jan Jansen hat das Ticket in einen Sprint gelegt.',
    )
  })

  test('in English', async () => {
    await i18n.changeLanguage('en')
    expect(systemText(i18n.t.bind(i18n), entry('ticket.title_changed'), 'en')).toBe(
      'Jan Jansen changed the title.',
    )
    expect(
      systemText(
        i18n.t.bind(i18n),
        entry('ticket.sprint_changed', { value: 's11', name: 'Sprint 11' }, null),
        'en',
      ),
    ).toBe('Jan Jansen moved the ticket from Sprint 11 to the backlog.')
  })
})
