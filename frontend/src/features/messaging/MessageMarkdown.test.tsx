import { render, screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { MessageMarkdown } from './MessageMarkdown'

describe('message markdown', () => {
  test('an image from elsewhere is not loaded, one of this installation is', () => {
    render(
      <MessageMarkdown
        markdown={
          '![fremd](https://tracker.example/pixel.png) ![auch](//cdn.example/x.png) ' +
          '![hier](/api/attachments/a1/download)'
        }
      />,
    )
    const images = screen.getAllByRole('img')
    expect(images.map((img) => img.getAttribute('src'))).toEqual(['/api/attachments/a1/download'])
    expect(screen.getByText('fremd')).toBeInTheDocument() // its text stays
  })
})
