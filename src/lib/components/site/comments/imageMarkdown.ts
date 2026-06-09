const imageExtensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif']

const markdownImageLinePattern =
  /^\s*!\[[^\]]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+["'][^"']*["'])?\s*\)\s*$/

const bareUrlLinePattern = /^\s*(https?:\/\/[^\s<>()]+|\/[^\s<>()]+)\s*$/i

const normalizeUrlToken = (token: string) => {
  const trimmed = token.trim()
  if (trimmed.startsWith('<') && trimmed.endsWith('>')) {
    return trimmed.slice(1, -1).trim()
  }
  return trimmed
}

export const isCommentImageUrl = (url: string) => {
  const normalized = normalizeUrlToken(url)
  if (!/^(https?:\/\/|\/)/i.test(normalized)) return false
  const path = normalized.split(/[?#]/)[0].toLowerCase()
  return imageExtensions.some((extension) => path.endsWith(extension))
}

const markdownImageUrlFromLine = (line: string) => {
  const match = line.match(markdownImageLinePattern)
  if (!match) return ''
  const url = normalizeUrlToken(match[1] || '')
  return isCommentImageUrl(url) ? url : ''
}

const bareImageUrlFromLine = (line: string) => {
  const match = line.match(bareUrlLinePattern)
  if (!match) return ''
  const url = normalizeUrlToken(match[1] || '')
  return isCommentImageUrl(url) ? url : ''
}

const compactBlankLines = (value: string) =>
  value
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

export const normalizeCommentImageMarkdown = (source: string) =>
  (source || '')
    .split(/\r?\n/)
    .map((line) => {
      if (markdownImageUrlFromLine(line)) return line.trim()
      const bareImageUrl = bareImageUrlFromLine(line)
      if (bareImageUrl) return `![](${bareImageUrl})`
      return line
    })
    .join('\n')
    .trim()

export const splitCommentBodyImages = (source: string) => {
  const textLines: string[] = []
  const imageUrls: string[] = []

  ;(source || '').split(/\r?\n/).forEach((line) => {
    const markdownImageUrl = markdownImageUrlFromLine(line)
    if (markdownImageUrl) {
      imageUrls.push(markdownImageUrl)
      return
    }

    const bareImageUrl = bareImageUrlFromLine(line)
    if (bareImageUrl) {
      imageUrls.push(bareImageUrl)
      return
    }

    textLines.push(line)
  })

  return {
    text: compactBlankLines(textLines.join('\n')),
    imageUrls: Array.from(new Set(imageUrls)),
  }
}

export const composeCommentBody = (text: string, imageUrls: string[]) => {
  const uniqueImages = Array.from(
    new Set(imageUrls.map((url) => normalizeUrlToken(url)).filter(isCommentImageUrl))
  )
  const normalizedText = normalizeCommentImageMarkdown(text || '')
  const imagesMarkdown = uniqueImages.map((url) => `![](${url})`).join('\n\n')
  return [normalizedText, imagesMarkdown].filter((part) => part.trim()).join('\n\n').trim()
}
