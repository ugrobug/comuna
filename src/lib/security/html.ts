import { getSafeUrl } from './url'

const ALLOWED_TAGS = new Set([
  'p',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'nav',
  'span',
  'b',
  'i',
  'em',
  'strong',
  'a',
  'button',
  'br',
  'ul',
  'ol',
  'li',
  'img',
  'audio',
  'source',
  'progress',
  'table',
  'thead',
  'tbody',
  'tr',
  'td',
  'th',
  'figure',
  'figcaption',
  'input',
  'blockquote',
  'footer',
  'div',
  'iframe',
  'pre',
  'code',
])

const VOID_TAGS = new Set(['br', 'img', 'source', 'input'])
const BOOLEAN_ATTRIBUTES = new Set(['allowfullscreen', 'controls', 'hidden'])

const GLOBAL_ATTRIBUTES = new Set([
  'class',
  'id',
  'role',
  'tabindex',
  'aria-expanded',
  'aria-label',
  'aria-pressed',
  'hidden',
  'data-compare-position',
  'data-poll-multiple',
  'data-poll-closed',
  'data-poll-locked',
  'data-poll-id',
  'data-rating-block-id',
  'data-rating-value',
  'data-music-provider',
  'data-spoiler-open',
  'data-post-link-id',
  'data-post-link-needs-hydration',
  'data-post-link-hydrated',
  'data-post-link-title',
  'data-post-link-text',
  'data-post-link-image',
  'data-glossary-term',
  'data-glossary-slug',
  'data-glossary-definition',
])

const TAG_ATTRIBUTES: Record<string, Set<string>> = {
  a: new Set(['href', 'target', 'rel', 'title', 'class', 'id', 'aria-label']),
  button: new Set(['type', 'class', 'data-rating-value', 'aria-pressed', 'aria-label']),
  audio: new Set(['src', 'controls', 'preload', 'class']),
  source: new Set(['src', 'type']),
  img: new Set([
    'src',
    'srcset',
    'sizes',
    'loading',
    'fetchpriority',
    'alt',
    'width',
    'height',
    'class',
    'title',
    'data-expandable-image',
    'data-expandable-src',
  ]),
  iframe: new Set(['src', 'allow', 'allowfullscreen', 'frameborder', 'referrerpolicy', 'loading', 'class', 'title']),
  input: new Set(['type', 'value', 'max', 'class', 'data-option-index']),
}

const ALLOWED_IFRAME_PREFIXES = [
  'https://t.me/',
  'https://www.openstreetmap.org/export/embed.html',
  'https://open.spotify.com/embed/',
  'https://w.soundcloud.com/player/',
  'https://music.yandex.ru/iframe/',
  'https://music.yandex.com/iframe/',
  'https://www.youtube.com/embed/',
  'https://youtube.com/embed/',
  'https://www.youtube-nocookie.com/embed/',
  'https://rutube.ru/play/embed/',
  'https://vk.com/video_ext.php',
  'https://player.vimeo.com/video/',
]

const DANGEROUS_CONTENT_TAGS =
  /<\s*(script|style|template|object|embed|svg|math|base|link|meta)\b[\s\S]*?<\s*\/\s*\1\s*>/gi
const HTML_COMMENTS = /<!--[\s\S]*?-->/g
const TAG_PATTERN = /<\/?([a-zA-Z][\w:-]*)([^<>]*)>/g
const ATTRIBUTE_PATTERN = /([^\s"'<>\/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g

const ENTITY_BY_NAME: Record<string, string> = {
  amp: '&',
  apos: "'",
  gt: '>',
  lt: '<',
  nbsp: ' ',
  quot: '"',
}

const decodeCodePoint = (codePoint: number, fallback: string) => {
  if (!Number.isFinite(codePoint) || codePoint < 0 || codePoint > 0x10ffff) return fallback
  try {
    return String.fromCodePoint(codePoint)
  } catch {
    return fallback
  }
}

const decodeHtmlEntities = (value: string) =>
  value.replace(/&(#x[a-f0-9]+|#\d+|[a-z]+);/gi, (match, entity: string) => {
    const normalized = entity.toLowerCase()
    if (normalized.startsWith('#x')) {
      const codePoint = Number.parseInt(normalized.slice(2), 16)
      return decodeCodePoint(codePoint, match)
    }
    if (normalized.startsWith('#')) {
      const codePoint = Number.parseInt(normalized.slice(1), 10)
      return decodeCodePoint(codePoint, match)
    }
    return ENTITY_BY_NAME[normalized] ?? match
  })

const escapeAttribute = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

const isAttributeAllowed = (tag: string, name: string) => {
  if (name.startsWith('on') || name === 'style' || name === 'srcdoc') return false
  return GLOBAL_ATTRIBUTES.has(name) || TAG_ATTRIBUTES[tag]?.has(name) || false
}

const isAllowedIframeSrc = (value: unknown) => {
  const url = getSafeUrl(decodeHtmlEntities(String(value ?? '')), { allowRelative: false })
  return Boolean(url && ALLOWED_IFRAME_PREFIXES.some((prefix) => url.startsWith(prefix)))
}

const sanitizeSrcSet = (value: unknown) =>
  String(value ?? '')
    .split(',')
    .map((candidate) => {
      const parts = candidate.trim().split(/\s+/)
      const url = getSafeUrl(decodeHtmlEntities(parts[0] ?? ''), {
        allowRelative: true,
        allowDataImage: true,
      })
      if (!url) return ''
      return [url, ...parts.slice(1)].join(' ')
    })
    .filter(Boolean)
    .join(', ')

const sanitizeAttributeValue = (tag: string, name: string, value: string) => {
  const decodedValue = decodeHtmlEntities(value)

  if (name === 'href') {
    return getSafeUrl(decodedValue, {
      allowedProtocols: ['http:', 'https:', 'mailto:'],
      allowRelative: true,
    })
  }

  if (name === 'src' || name === 'data-expandable-src') {
    const safeUrl = getSafeUrl(decodedValue, {
      allowRelative: tag !== 'iframe',
      allowDataImage: tag === 'img',
    })
    if (tag === 'iframe' && !isAllowedIframeSrc(safeUrl)) return null
    return safeUrl
  }

  if (name === 'srcset') return sanitizeSrcSet(decodedValue)

  return decodedValue
}

const collectAttributes = (tag: string, source: string) => {
  const attributes: Array<[string, string | null]> = []
  ATTRIBUTE_PATTERN.lastIndex = 0

  for (const match of source.matchAll(ATTRIBUTE_PATTERN)) {
    const name = match[1]?.toLowerCase()
    if (!name || !isAttributeAllowed(tag, name)) continue

    const rawValue = match[2] ?? match[3] ?? match[4] ?? null
    if (rawValue === null && BOOLEAN_ATTRIBUTES.has(name)) {
      attributes.push([name, null])
      continue
    }
    if (rawValue === null) continue

    const safeValue = sanitizeAttributeValue(tag, name, rawValue)
    if (safeValue === null || safeValue === '') continue
    attributes.push([name, safeValue])
  }

  if (tag === 'a') {
    const href = attributes.find(([name]) => name === 'href')?.[1]
    const relIndex = attributes.findIndex(([name]) => name === 'rel')
    const relParts = new Set(
      relIndex >= 0 && attributes[relIndex][1]
        ? String(attributes[relIndex][1]).split(/\s+/).filter(Boolean)
        : []
    )
    if (typeof href === 'string' && href.includes('t.me/')) {
      relParts.add('nofollow')
      relParts.add('noopener')
    }
    if (relParts.size && relIndex >= 0) attributes[relIndex] = ['rel', Array.from(relParts).join(' ')]
    if (relParts.size && relIndex < 0) attributes.push(['rel', Array.from(relParts).join(' ')])
  }

  if (tag === 'iframe' && !attributes.some(([name]) => name === 'src')) return null

  return attributes
    .map(([name, value]) => (value === null ? name : `${name}="${escapeAttribute(value)}"`))
    .join(' ')
}

export const sanitizePostHtml = (html: string) =>
  String(html ?? '')
    .replace(DANGEROUS_CONTENT_TAGS, '')
    .replace(HTML_COMMENTS, '')
    .replace(TAG_PATTERN, (match, rawTagName: string, rawAttributes: string) => {
      const tagName = rawTagName.toLowerCase()
      if (!ALLOWED_TAGS.has(tagName)) return ''

      const isClosingTag = /^<\s*\//.test(match)
      if (isClosingTag) return VOID_TAGS.has(tagName) ? '' : `</${tagName}>`

      const attributes = collectAttributes(tagName, rawAttributes)
      if (attributes === null) return ''

      return attributes ? `<${tagName} ${attributes}>` : `<${tagName}>`
    })
