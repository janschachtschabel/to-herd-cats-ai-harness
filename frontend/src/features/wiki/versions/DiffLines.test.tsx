import { render } from '@testing-library/react'
import { expect, test } from 'vitest'
import { DiffLines } from './DiffLines'

test('a long line wraps beside its mark, not under it (narrow screens)', () => {
  const { container } = render(
    <DiffLines
      hunks={[
        { kind: 'equal', lines: ['Protokolle beginnen mit Datum, Anwesenden und Thema.'] },
        { kind: 'insert', lines: ['Am Ende steht der nächste Termin.'] },
      ]}
    />,
  )
  const line = container.querySelector('ins')!
  // The mark is a column of its own; the text wraps in the other one.
  expect(line).toHaveClass('flex')
  const [mark, text] = Array.from(line.children)
  expect(mark).toHaveAttribute('aria-hidden')
  expect(mark).toHaveClass('shrink-0')
  expect(text).toHaveTextContent('hinzugefügt: Am Ende steht der nächste Termin.')
  expect(text).toHaveClass('min-w-0', 'whitespace-pre-wrap')
})
