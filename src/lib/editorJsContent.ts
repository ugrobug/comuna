export type EditorJsPayload = {
  blocks: Array<Record<string, any>>
  [key: string]: any
}

export const isEditorJsPayload = (value: unknown): value is EditorJsPayload =>
  !!value && typeof value === 'object' && Array.isArray((value as any).blocks)

const encodeEditorPayload = (payload: EditorJsPayload): string => {
  const json = JSON.stringify(payload)
  const bufferCtor = (globalThis as any)?.Buffer
  if (bufferCtor) {
    return bufferCtor.from(json, 'utf-8').toString('base64')
  }
  return btoa(unescape(encodeURIComponent(json)))
}

const decodeEditorPayload = (value: string): unknown => {
  const raw = String(value || '').trim()
  if (!raw) return null

  try {
    return JSON.parse(raw)
  } catch {
    const bufferCtor = (globalThis as any)?.Buffer
    const json = bufferCtor
      ? bufferCtor.from(raw, 'base64').toString('utf-8')
      : decodeURIComponent(escape(atob(raw)))
    return JSON.parse(json)
  }
}

export const parseEditorJsPayload = (value: string): EditorJsPayload | null => {
  try {
    const decoded = decodeEditorPayload(value)
    return isEditorJsPayload(decoded) ? decoded : null
  } catch {
    return null
  }
}

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const decodeEntities = (value: string) =>
  value
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")

const stripTags = (value: string) =>
  decodeEntities(value.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim())

const getInnerHtml = (html: string) =>
  html.replace(/^<[^>]+>/, '').replace(/<\/[^>]+>$/, '').trim()

const getAttribute = (html: string, name: string) => {
  const match = html.match(new RegExp(`${name}\\s*=\\s*("([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i'))
  return decodeEntities(match?.[2] ?? match?.[3] ?? match?.[4] ?? '').trim()
}

const paragraphBlock = (text: string) => ({
  type: 'paragraph',
  data: { text },
})

const htmlToEditorPayload = (value: string): EditorJsPayload => {
  const source = String(value || '').trim()
  if (!source) return { blocks: [] }

  if (!/<[a-z][\s\S]*>/i.test(source)) {
    return {
      blocks: source
        .split(/\n{2,}/)
        .map((part) => part.trim())
        .filter(Boolean)
        .map((part) => paragraphBlock(escapeHtml(part).replace(/\n/g, '<br>'))),
    }
  }

  const blocks: Array<Record<string, any>> = []
  const addPlainSegment = (segment: string) => {
    const text = stripTags(segment)
    if (text) {
      blocks.push(paragraphBlock(escapeHtml(text)))
    }
  }

  const addImageBlock = (html: string, caption = '') => {
    const img = html.match(/<img\b[^>]*>/i)?.[0] || ''
    const url = getAttribute(img, 'src')
    if (!url) return

    const finalCaption = caption || ''
    blocks.push({
      type: 'image',
      data: {
        file: {
          url,
          alt: getAttribute(img, 'alt') || finalCaption,
          title: getAttribute(img, 'title'),
        },
        caption: finalCaption,
      },
    })
  }

  const blockRegex = /<(h[1-6]|p|blockquote|pre|ul|ol|figure)\b[\s\S]*?<\/\1>|<img\b[^>]*>/gi
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = blockRegex.exec(source))) {
    addPlainSegment(source.slice(lastIndex, match.index))

    const html = match[0]
    const tag = (match[1] || 'img').toLowerCase()
    const inner = getInnerHtml(html)

    if (tag.startsWith('h')) {
      const text = inner.trim()
      if (text) {
        blocks.push({
          type: 'header',
          data: { text, level: Number(tag.slice(1)) || 2 },
        })
      }
    } else if (tag === 'p') {
      if (inner) blocks.push(paragraphBlock(inner))
    } else if (tag === 'blockquote') {
      const text = inner.trim()
      if (text) blocks.push({ type: 'quote', data: { text, caption: '' } })
    } else if (tag === 'pre') {
      const code = stripTags(inner)
      if (code) blocks.push({ type: 'code', data: { code } })
    } else if (tag === 'ul' || tag === 'ol') {
      const items = Array.from(inner.matchAll(/<li\b[^>]*>([\s\S]*?)<\/li>/gi))
        .map((item) => item[1]?.trim())
        .filter(Boolean)
      if (items.length) {
        blocks.push({
          type: 'list',
          data: { style: tag === 'ol' ? 'ordered' : 'unordered', items },
        })
      }
    } else if (tag === 'figure') {
      const caption = stripTags(html.match(/<figcaption\b[^>]*>([\s\S]*?)<\/figcaption>/i)?.[1] || '')
      addImageBlock(html, caption)
    } else {
      addImageBlock(html)
    }

    lastIndex = match.index + html.length
  }

  addPlainSegment(source.slice(lastIndex))

  if (!blocks.length) {
    blocks.push(paragraphBlock(source))
  }

  return { blocks }
}

export const normalizeEditorJsContent = (value: string): string => {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const payload = parseEditorJsPayload(raw)
  if (payload) return raw
  return encodeEditorPayload(htmlToEditorPayload(raw))
}
