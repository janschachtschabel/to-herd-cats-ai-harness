import type { Attachment } from '@/lib/api'

const IMAGE = /^image\/(png|jpeg|gif|webp)$/

/** The Markdown that shows (images) or links (other files) the attachment in a page. */
export function attachmentMarkdown(attachment: Attachment): string {
  const name = attachment.filename.replace(/[[\]]/g, '')
  return IMAGE.test(attachment.mime)
    ? `![${name}](${attachment.url}?inline=1)`
    : `[${name}](${attachment.url})`
}
