import type { Handle } from '@sveltejs/kit'

const PRIORITY_HEAD_TAG_PATTERN =
  /<(?:meta|link)\b[^>]*(?:name="description"|rel="canonical"|property="og:[^"]+"|name="twitter:[^"]+")[^>]*>/gi

const STYLESHEET_LINK_PATTERN = /<link\b[^>]*rel="stylesheet"[^>]*>/i

const securityHeaders = {
  'Content-Security-Policy': [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'self'",
    "form-action 'self'",
    "img-src 'self' data: blob: https:",
    "media-src 'self' data: blob: https:",
    "font-src 'self' data: https:",
    "style-src 'self' 'unsafe-inline' https:",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://telegram.org https://oauth.telegram.org https://vk.com https://*.vk.com https://mc.yandex.ru https://www.googletagmanager.com https://www.google-analytics.com",
    "connect-src 'self' https: wss:",
    "frame-src 'self' https://telegram.org https://oauth.telegram.org https://vk.com https://*.vk.com https://vk.ru https://*.vk.ru https://www.youtube.com https://www.youtube-nocookie.com https://youtube.com https://player.vimeo.com https://open.spotify.com https://www.openstreetmap.org",
    "worker-src 'self' blob:",
  ].join('; '),
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'SAMEORIGIN',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
}

const prioritizePreviewHeadTags = (html: string) => {
  const headOpenIndex = html.indexOf('<head>')
  const headCloseIndex = html.indexOf('</head>')
  if (headOpenIndex === -1 || headCloseIndex === -1 || headCloseIndex <= headOpenIndex) {
    return html
  }

  const headContentStart = html.indexOf('>', headOpenIndex)
  if (headContentStart === -1) return html

  const headContent = html.slice(headContentStart + 1, headCloseIndex)
  const priorityTags: string[] = []
  const strippedHeadContent = headContent.replace(PRIORITY_HEAD_TAG_PATTERN, (match) => {
    priorityTags.push(match)
    return ''
  })

  if (!priorityTags.length) return html

  const insertionIndex = strippedHeadContent.search(STYLESHEET_LINK_PATTERN)
  if (insertionIndex === -1) return html

  const reorderedHeadContent =
    strippedHeadContent.slice(0, insertionIndex) +
    priorityTags.join('') +
    strippedHeadContent.slice(insertionIndex)

  return (
    html.slice(0, headContentStart + 1) +
    reorderedHeadContent +
    html.slice(headCloseIndex)
  )
}

export const handle: Handle = async ({ event, resolve }) => {
  const shouldPrioritizePreviewHead = event.url.pathname.startsWith('/b/post/')
  const response = await resolve(
    event,
    shouldPrioritizePreviewHead
      ? {
          transformPageChunk: ({ html }) => prioritizePreviewHeadTags(html),
        }
      : undefined
  )
  const headers = new Headers(response.headers)
  for (const [name, value] of Object.entries(securityHeaders)) {
    headers.set(name, value)
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  })
}
