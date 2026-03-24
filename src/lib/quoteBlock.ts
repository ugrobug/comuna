export type NormalizedQuoteBlockData = {
  text: string
  caption: string
  authorName: string
  authorPhoto: string
}

const trimString = (value: unknown) => (typeof value === 'string' ? value.trim() : '')

const stripHtml = (value: string) =>
  value
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()

const escapeAttribute = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

export const normalizeQuoteBlockData = (value: unknown): NormalizedQuoteBlockData => {
  const data = value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
  return {
    text: trimString(data.text),
    caption: trimString(data.caption),
    authorName: trimString(data.author_name ?? data.authorName ?? data.author),
    authorPhoto: trimString(data.author_photo ?? data.authorPhoto),
  }
}

export const renderQuoteBlockHtml = (
  value: unknown,
  options?: { anchorId?: string }
) => {
  const { text, caption, authorName, authorPhoto } = normalizeQuoteBlockData(value)
  if (!text && !caption && !authorName && !authorPhoto) return ''

  const authorAlt = stripHtml(authorName) || 'Автор цитаты'
  const authorPhotoHtml = authorPhoto
    ? `<img class="post-quote__author-photo" src="${escapeAttribute(authorPhoto)}" alt="${escapeAttribute(authorAlt)}" loading="lazy" />`
    : ''
  const authorNameHtml = authorName
    ? `<div class="post-quote__author-name">${authorName}</div>`
    : ''
  const authorHtml =
    authorPhotoHtml || authorNameHtml
      ? `<div class="post-quote__author">${authorPhotoHtml}${authorNameHtml}</div>`
      : ''
  const footerHtml =
    caption || authorHtml
      ? `<footer class="post-quote__footer">${caption ? `<div class="post-quote__caption">${caption}</div>` : ''}${authorHtml}</footer>`
      : ''

  return `<blockquote${options?.anchorId || ''}>${text ? `<p>${text}</p>` : ''}${footerHtml}</blockquote>`
}
