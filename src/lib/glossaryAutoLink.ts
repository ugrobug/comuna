import { parseEditorJsPayload, type EditorJsPayload } from '$lib/editorJsContent'

export type GlossaryAutoLinkTerm = {
  id?: number | string
  term: string
  slug?: string
  definition: string
}

export type GlossaryAutoLinkMatch = {
  id: string
  term: string
  slug: string
  definition: string
  matchedText: string
  context: string
}

const TEXT_FIELD_KEYS = new Set([
  'caption',
  'content',
  'description',
  'message',
  'text',
  'title',
])

const SKIP_ANCESTOR_SELECTOR = '.post-glossary-term, a, code, pre'
const MAX_MATCHES = 200
const CONTEXT_RADIUS = 56

const normalizeTermKey = (value: string) => value.trim().toLocaleLowerCase('ru-RU')

const encodeEditorPayload = (payload: EditorJsPayload): string => {
  const json = JSON.stringify(payload)
  const bufferCtor = (globalThis as any)?.Buffer
  if (bufferCtor) {
    return bufferCtor.from(json, 'utf-8').toString('base64')
  }
  return btoa(unescape(encodeURIComponent(json)))
}

const isWordChar = (value: string) => /[\p{L}\p{N}_]/u.test(value)

const escapeAttrPart = (value: string) =>
  value
    .replace(/\\/g, '\\\\')
    .replace(/:/g, '\\:')
    .replace(/\./g, '\\.')

const normalizeTerms = (terms: GlossaryAutoLinkTerm[]) => {
  const seen = new Set<string>()
  return terms
    .map((term) => ({
      term: String(term.term || '').trim(),
      slug: String(term.slug || term.id || term.term || '').trim(),
      definition: String(term.definition || '').trim(),
    }))
    .filter((term) => term.term && term.definition)
    .filter((term) => {
      const key = normalizeTermKey(term.term)
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .sort((a, b) => b.term.length - a.term.length || a.term.localeCompare(b.term))
}

const shouldProcessStringKey = (key: string) => TEXT_FIELD_KEYS.has(key)

const makeContext = (text: string, start: number, end: number) => {
  const from = Math.max(0, start - CONTEXT_RADIUS)
  const to = Math.min(text.length, end + CONTEXT_RADIUS)
  const prefix = from > 0 ? '...' : ''
  const suffix = to < text.length ? '...' : ''
  return `${prefix}${text.slice(from, to).replace(/\s+/g, ' ').trim()}${suffix}`
}

const matchTermsInText = (
  text: string,
  terms: ReturnType<typeof normalizeTerms>,
  targetId: string,
  textNodeIndex: number
) => {
  const lowerText = normalizeTermKey(text)
  const occupied: Array<{ start: number; end: number }> = []
  const matches: Array<GlossaryAutoLinkMatch & { start: number; end: number }> = []

  for (const term of terms) {
    const lowerTerm = normalizeTermKey(term.term)
    let index = lowerText.indexOf(lowerTerm)

    while (index !== -1) {
      const end = index + lowerTerm.length
      const previousChar = index > 0 ? text[index - 1] : ''
      const nextChar = end < text.length ? text[end] : ''
      const startsWithWord = isWordChar(term.term[0] || '')
      const endsWithWord = isWordChar(term.term[term.term.length - 1] || '')
      const hasWordBoundaryBefore = !startsWithWord || !previousChar || !isWordChar(previousChar)
      const hasWordBoundaryAfter = !endsWithWord || !nextChar || !isWordChar(nextChar)
      const overlaps = occupied.some((range) => index < range.end && end > range.start)

      if (hasWordBoundaryBefore && hasWordBoundaryAfter && !overlaps) {
        occupied.push({ start: index, end })
        matches.push({
          id: `${targetId}:${textNodeIndex}:${index}:${end}:${escapeAttrPart(term.slug)}`,
          term: term.term,
          slug: term.slug,
          definition: term.definition,
          matchedText: text.slice(index, end),
          context: makeContext(text, index, end),
          start: index,
          end,
        })
      }

      index = lowerText.indexOf(lowerTerm, index + lowerTerm.length)
    }
  }

  return matches.sort((a, b) => a.start - b.start || b.end - a.end)
}

const parseHtmlFragment = (value: string) => {
  const template = document.createElement('template')
  template.innerHTML = value
  return template
}

const walkTextNodes = (
  root: ParentNode,
  callback: (node: Text, textNodeIndex: number) => void
) => {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement
      if (parent?.closest(SKIP_ANCESTOR_SELECTOR)) return NodeFilter.FILTER_REJECT
      if (!node.textContent?.trim()) return NodeFilter.FILTER_REJECT
      return NodeFilter.FILTER_ACCEPT
    },
  })
  let textNodeIndex = 0
  let node = walker.nextNode()
  while (node) {
    callback(node as Text, textNodeIndex)
    textNodeIndex += 1
    node = walker.nextNode()
  }
}

const collectStringMatches = (
  value: string,
  terms: ReturnType<typeof normalizeTerms>,
  targetId: string
) => {
  const template = parseHtmlFragment(value)
  const matches: GlossaryAutoLinkMatch[] = []
  walkTextNodes(template.content, (node, textNodeIndex) => {
    matches.push(...matchTermsInText(node.textContent || '', terms, targetId, textNodeIndex))
  })
  return matches
}

const applyStringMatches = (
  value: string,
  terms: ReturnType<typeof normalizeTerms>,
  targetId: string,
  selectedIds: Set<string>
) => {
  const template = parseHtmlFragment(value)
  const nodes: Array<{ node: Text; matches: Array<GlossaryAutoLinkMatch & { start: number; end: number }> }> = []

  walkTextNodes(template.content, (node, textNodeIndex) => {
    const matches = matchTermsInText(node.textContent || '', terms, targetId, textNodeIndex).filter((match) =>
      selectedIds.has(match.id)
    )
    if (matches.length) {
      nodes.push({ node, matches })
    }
  })

  if (!nodes.length) return value

  for (const { node, matches } of nodes) {
    const text = node.textContent || ''
    const fragment = document.createDocumentFragment()
    let cursor = 0

    for (const match of matches) {
      if (match.start > cursor) {
        fragment.appendChild(document.createTextNode(text.slice(cursor, match.start)))
      }
      const span = document.createElement('span')
      span.className = 'post-glossary-term'
      span.setAttribute('data-glossary-term', match.term)
      span.setAttribute('data-glossary-slug', match.slug)
      span.setAttribute('data-glossary-definition', match.definition)
      span.setAttribute('title', match.definition)
      span.textContent = text.slice(match.start, match.end)
      fragment.appendChild(span)
      cursor = match.end
    }

    if (cursor < text.length) {
      fragment.appendChild(document.createTextNode(text.slice(cursor)))
    }
    node.parentNode?.replaceChild(fragment, node)
  }

  return template.innerHTML
}

const walkEditorDataStrings = (
  value: unknown,
  path: string[],
  callback: (holder: Record<string, unknown> | unknown[], key: string | number, value: string, path: string[]) => void
) => {
  if (!value || typeof value !== 'object') return

  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      const nextPath = [...path, String(index)]
      if (typeof item === 'string') {
        callback(value, index, item, nextPath)
      } else {
        walkEditorDataStrings(item, nextPath, callback)
      }
    })
    return
  }

  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    const nextPath = [...path, key]
    if (typeof item === 'string') {
      if (shouldProcessStringKey(key)) {
        callback(value as Record<string, unknown>, key, item, nextPath)
      }
    } else if (key === 'items' || key === 'data') {
      walkEditorDataStrings(item, nextPath, callback)
    } else if (typeof item === 'object' && item !== null && shouldProcessStringKey(key)) {
      walkEditorDataStrings(item, nextPath, callback)
    }
  }
}

const decodeEditorContent = (content: string) => {
  return parseEditorJsPayload(content)
}

export const findGlossaryAutoLinkMatches = (
  content: string,
  terms: GlossaryAutoLinkTerm[]
): GlossaryAutoLinkMatch[] => {
  if (typeof document === 'undefined') return []
  const editorData = decodeEditorContent(content)
  if (!editorData) return []

  const normalizedTerms = normalizeTerms(terms)
  if (!normalizedTerms.length) return []

  const matches: GlossaryAutoLinkMatch[] = []
  for (const [blockIndex, block] of (editorData.blocks || []).entries()) {
    walkEditorDataStrings(block?.data, [`blocks`, String(blockIndex), 'data'], (_holder, _key, value, path) => {
      if (matches.length >= MAX_MATCHES) return
      const targetId = path.join('.')
      const nextMatches = collectStringMatches(value, normalizedTerms, targetId)
      matches.push(...nextMatches.slice(0, MAX_MATCHES - matches.length))
    })
    if (matches.length >= MAX_MATCHES) break
  }

  return matches
}

export const applyGlossaryAutoLinkMatches = (
  content: string,
  terms: GlossaryAutoLinkTerm[],
  selectedMatchIds: string[]
) => {
  if (typeof document === 'undefined') return content
  const editorData = decodeEditorContent(content)
  if (!editorData) return content

  const normalizedTerms = normalizeTerms(terms)
  const selectedIds = new Set(selectedMatchIds)
  if (!normalizedTerms.length || !selectedIds.size) return content

  const nextData = JSON.parse(JSON.stringify(editorData))
  for (const [blockIndex, block] of (nextData.blocks || []).entries()) {
    walkEditorDataStrings(block?.data, [`blocks`, String(blockIndex), 'data'], (holder, key, value, path) => {
      const targetId = path.join('.')
      const nextValue = applyStringMatches(value, normalizedTerms, targetId, selectedIds)
      if (Array.isArray(holder) && typeof key === 'number') {
        holder[key] = nextValue
      } else if (!Array.isArray(holder) && typeof key === 'string') {
        holder[key] = nextValue
      }
    })
  }

  return encodeEditorPayload(nextData)
}
