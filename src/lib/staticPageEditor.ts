import { deserializeEditorModel } from '$lib/util'

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const isEditorJsPayload = (value: unknown): value is { blocks: Array<Record<string, any>> } =>
  !!value && typeof value === 'object' && Array.isArray((value as any).blocks)

const parseEditorJsPayload = (value: string) => {
  const raw = String(value || '').trim()
  if (!raw) return null

  try {
    const parsed = JSON.parse(raw)
    return isEditorJsPayload(parsed) ? parsed : null
  } catch {
    try {
      const decoded = deserializeEditorModel(raw)
      return isEditorJsPayload(decoded) ? decoded : null
    } catch {
      return null
    }
  }
}

const renderListItems = (items: any[] = [], ordered = false): string => {
  const tag = ordered ? 'ol' : 'ul'
  const rendered = items
    .map((item) => {
      if (typeof item === 'string') {
        return `<li>${item}</li>`
      }
      if (!item || typeof item !== 'object') {
        return ''
      }

      const content = typeof item.content === 'string' ? item.content : ''
      const children = Array.isArray(item.items) && item.items.length
        ? renderListItems(item.items, ordered)
        : ''
      return `<li>${content}${children}</li>`
    })
    .filter(Boolean)
    .join('')

  return rendered ? `<${tag}>${rendered}</${tag}>` : ''
}

const renderTable = (rows: any[] = []): string => {
  const body = rows
    .map((row) => {
      if (!Array.isArray(row)) return ''
      const cells = row.map((cell) => `<td>${String(cell ?? '')}</td>`).join('')
      return cells ? `<tr>${cells}</tr>` : ''
    })
    .filter(Boolean)
    .join('')

  return body ? `<table><tbody>${body}</tbody></table>` : ''
}

const renderBlock = (block: Record<string, any>) => {
  const type = String(block?.type || '').toLowerCase()
  const data = block?.data ?? {}

  switch (type) {
    case 'paragraph':
      return data?.text ? `<p>${data.text}</p>` : ''
    case 'header': {
      const level = Math.min(Math.max(Number(data?.level) || 2, 1), 6)
      return data?.text ? `<h${level}>${data.text}</h${level}>` : ''
    }
    case 'list': {
      const items = Array.isArray(data?.items) ? data.items : []
      const ordered = String(data?.style || '').toLowerCase() === 'ordered'
      return renderListItems(items, ordered)
    }
    case 'quote': {
      const text = typeof data?.text === 'string' ? data.text.trim() : ''
      const caption = typeof data?.caption === 'string' ? data.caption.trim() : ''
      if (!text && !caption) return ''
      return `<blockquote>${text ? `<p>${text}</p>` : ''}${caption ? `<footer>${caption}</footer>` : ''}</blockquote>`
    }
    case 'delimiter':
      return '<hr />'
    case 'code':
      return data?.code ? `<pre><code>${escapeHtml(String(data.code))}</code></pre>` : ''
    case 'table':
      return renderTable(Array.isArray(data?.content) ? data.content : [])
    case 'raw':
    case 'html':
      return typeof data?.html === 'string' ? data.html : ''
    case 'image': {
      const imageUrl =
        typeof data?.file?.url === 'string'
          ? data.file.url
          : typeof data?.url === 'string'
            ? data.url
            : ''
      if (!imageUrl) return ''

      const caption = typeof data?.caption === 'string' ? data.caption.trim() : ''
      const alt = caption || 'Изображение'
      return `<figure><img src="${imageUrl}" alt="${escapeHtml(alt)}" />${caption ? `<figcaption>${caption}</figcaption>` : ''}</figure>`
    }
    default: {
      const text = Object.values(data)
        .filter((item) => typeof item === 'string')
        .map((item) => String(item).trim())
        .filter(Boolean)
        .join(' ')
      return text ? `<p>${text}</p>` : ''
    }
  }
}

export const normalizeStaticPageEditorValue = (value: string) => {
  const payload = parseEditorJsPayload(value)
  if (!payload) return value

  return payload.blocks.map(renderBlock).filter(Boolean).join('\n')
}
