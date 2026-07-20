import type { Handle } from '@sveltejs/kit'
import { brandNameForLanguage } from '$lib/brand'
import {
  languageFromAcceptLanguage,
  languageFromPathname,
  originalPostLanguage,
  postLanguageLocales,
  type PostLanguageCode,
} from '$lib/postLanguages'

const PRIORITY_HEAD_TAG_PATTERN =
  /<(?:meta|link)\b[^>]*(?:name="description"|name="robots"|rel="canonical"|property="og:[^"]+"|name="twitter:[^"]+")[^>]*>/gi

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
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://telegram.org https://oauth.telegram.org https://vk.com https://*.vk.com https://accounts.google.com https://appleid.cdn-apple.com https://mc.yandex.ru https://www.googletagmanager.com https://www.google-analytics.com https://pagead2.googlesyndication.com https://partner.googleadservices.com",
    "connect-src 'self' https: wss:",
    "frame-src 'self' https://telegram.org https://oauth.telegram.org https://vk.com https://*.vk.com https://vk.ru https://*.vk.ru https://accounts.google.com https://appleid.apple.com https://www.youtube.com https://www.youtube-nocookie.com https://youtube.com https://player.vimeo.com https://open.spotify.com https://www.openstreetmap.org https://googleads.g.doubleclick.net https://tpc.googlesyndication.com https://pagead2.googlesyndication.com",
    "worker-src 'self' blob:",
  ].join('; '),
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'SAMEORIGIN',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
}

export const prioritizePreviewHeadTags = (html: string) => {
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

const escapeHtmlAttribute = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

const localizeAppShellHead = (html: string, language: PostLanguageCode) => {
  const brandName = escapeHtmlAttribute(brandNameForLanguage(language))
  const htmlLanguage = escapeHtmlAttribute(postLanguageLocales[language] || postLanguageLocales.ru)

  return html
    .replace(/<html\b([^>]*)\blang="[^"]*"/i, `<html$1lang="${htmlLanguage}"`)
    .replace(
      /<meta\s+name="application-name"\s+content="[^"]*"\s*\/?>/i,
      `<meta name="application-name" content="${brandName}" />`
    )
    .replace(
      /<meta\s+name="apple-mobile-web-app-title"\s+content="[^"]*"\s*\/?>/i,
      `<meta name="apple-mobile-web-app-title" content="${brandName}" />`
    )
}

export const handle: Handle = async ({ event, resolve }) => {
  const language =
    languageFromPathname(event.url.pathname) ||
    languageFromAcceptLanguage(event.request.headers.get('Accept-Language')) ||
    originalPostLanguage
  const shouldPrioritizePreviewHead = /^\/(?:[a-z]{2}\/)?b\/post\//.test(event.url.pathname)
  const response = await resolve(event, {
    transformPageChunk: ({ html }) => {
      const localizedHtml = localizeAppShellHead(html, language)
      return shouldPrioritizePreviewHead
        ? prioritizePreviewHeadTags(localizedHtml)
        : localizedHtml
    },
  })
  const headers = new Headers(response.headers)
  for (const [name, value] of Object.entries(securityHeaders)) {
    headers.set(name, value)
  }
  if (
    shouldPrioritizePreviewHead &&
    response.headers.get('content-type')?.includes('text/html')
  ) {
    headers.delete('link')
    headers.set('content-type', 'text/html; charset=utf-8')
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  })
}
