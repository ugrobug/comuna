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

const TITLE_TAG_PATTERN = /<title\b[^>]*>[\s\S]*?<\/title>/i

const TITLE_CONTENT_PATTERN = /<title\b[^>]*>([\s\S]*?)<\/title>/i

const STYLESHEET_LINK_PATTERN = /<link\b[^>]*rel="stylesheet"[^>]*>/i

const SOCIAL_CRAWLER_USER_AGENT_PATTERN =
  /\b(?:TelegramBot|Twitterbot|facebookexternalhit|Facebot|WhatsApp|Slackbot|Discordbot|LinkedInBot|Pinterest|vkShare|SkypeUriPreview|Applebot)\b/i

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
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://telegram.org https://oauth.telegram.org https://vk.com https://*.vk.com https://mc.yandex.ru https://www.googletagmanager.com https://www.google-analytics.com https://pagead2.googlesyndication.com https://partner.googleadservices.com",
    "connect-src 'self' https: wss:",
    "frame-src 'self' https://telegram.org https://oauth.telegram.org https://vk.com https://*.vk.com https://vk.ru https://*.vk.ru https://www.youtube.com https://www.youtube-nocookie.com https://youtube.com https://player.vimeo.com https://open.spotify.com https://www.openstreetmap.org https://googleads.g.doubleclick.net https://tpc.googlesyndication.com https://pagead2.googlesyndication.com",
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

export const buildSocialCrawlerHtml = (html: string) => {
  const titleTag = html.match(TITLE_TAG_PATTERN)?.[0] || ''
  const titleContent = titleTag.match(TITLE_CONTENT_PATTERN)?.[1]?.trim() || ''
  const priorityTags = html.match(PRIORITY_HEAD_TAG_PATTERN) || []
  const hasRobotsTag = priorityTags.some((tag) => /\bname="robots"/i.test(tag))
  const robotsTag = hasRobotsTag ? '' : '<meta name="robots" content="max-image-preview:large">'
  const headTags = [
    '<meta charset="utf-8">',
    titleTag,
    robotsTag,
    ...priorityTags,
  ].filter(Boolean)

  const descriptionTag = priorityTags.find((tag) =>
    /(?:\bproperty="og:description"|\bname="description")/i.test(tag)
  )
  const descriptionContent = descriptionTag?.match(/\bcontent="([^"]*)"/i)?.[1]?.trim() || ''
  const imageTag = priorityTags.find((tag) => /\bproperty="og:image"/i.test(tag))
  const imageUrl = imageTag?.match(/\bcontent="([^"]*)"/i)?.[1]?.trim() || ''
  const bodyParts = [
    titleContent ? `<h1>${titleContent}</h1>` : '',
    descriptionContent ? `<p>${descriptionContent}</p>` : '',
    imageUrl ? `<img src="${imageUrl}" alt="">` : '',
  ].filter(Boolean)

  return `<!doctype html><html><head>${headTags.join('')}</head><body><main><article>${bodyParts.join('')}</article></main></body></html>`
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
  const isSocialCrawler =
    shouldPrioritizePreviewHead &&
    SOCIAL_CRAWLER_USER_AGENT_PATTERN.test(event.request.headers.get('User-Agent') || '')
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
  if (shouldPrioritizePreviewHead) {
    const vary = headers.get('vary')
    const varyValues = vary?.split(',').map((value) => value.trim().toLowerCase()) || []
    if (!varyValues.includes('user-agent')) {
      headers.set('vary', vary ? `${vary}, User-Agent` : 'User-Agent')
    }
  }
  if (
    isSocialCrawler &&
    response.status >= 200 &&
    response.status < 400 &&
    response.headers.get('content-type')?.includes('text/html')
  ) {
    const html = await response.text()
    const crawlerHtml = buildSocialCrawlerHtml(html)
    headers.delete('etag')
    headers.delete('link')
    headers.set('content-type', 'text/html; charset=utf-8')
    headers.set('content-length', String(new TextEncoder().encode(crawlerHtml).byteLength))
    headers.set('cache-control', 'public, max-age=300, stale-while-revalidate=300')
    return new Response(crawlerHtml, {
      status: response.status,
      statusText: response.statusText,
      headers,
    })
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  })
}
