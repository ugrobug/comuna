import type { Handle, HandleFetch } from '@sveltejs/kit'
import { SearchBackendProxy } from '$lib/server/SearchBackendProxy'
import type { AuthBootstrap } from '$lib/authBootstrap'
import { brandNameForLanguage } from '$lib/brand'
import {
  languageFromAcceptLanguage,
  languageFromPathname,
  normalizeInterfaceLanguage,
  originalPostLanguage,
  postLanguageLocales,
  type PostLanguageCode,
} from '$lib/postLanguages'
import { runWithRequestTranslations } from '$lib/server/requestTranslations'

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
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:",
    "connect-src 'self' https: wss:",
    "frame-src 'self' https://telegram.org https://oauth.telegram.org https://vk.com https://*.vk.com https://vk.ru https://*.vk.ru https://accounts.google.com https://appleid.apple.com https://www.youtube.com https://www.youtube-nocookie.com https://youtube.com https://player.vimeo.com https://open.spotify.com https://www.openstreetmap.org https://googleads.g.doubleclick.net https://tpc.googlesyndication.com https://pagead2.googlesyndication.com https://fundingchoicesmessages.google.com https://*.fundingchoicesmessages.google.com",
    "worker-src 'self' blob:",
  ].join('; '),
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'SAMEORIGIN',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
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

const hasSiteAuthentication = (request: Request) => {
  const cookie = request.headers.get('cookie') || ''
  const authorization = request.headers.get('authorization') || ''
  return /(?:^|;\s*)comuna_site_token=/.test(cookie) || Boolean(authorization)
}

const loadAuthBootstrap = async (event: Parameters<Handle>[0]['event']) => {
  if (!hasSiteAuthentication(event.request)) return null

  const cookie = event.request.headers.get('cookie') || ''
  const authorization = event.request.headers.get('authorization') || ''
  const headers = new Headers({ Accept: 'application/json' })
  if (cookie) headers.set('Cookie', cookie)
  if (authorization) headers.set('Authorization', authorization)

  try {
    const backendBaseUrl = (
      process.env.INTERNAL_BACKEND_URL ||
      process.env.PUBLIC_BACKEND_URL ||
      event.url.origin
    ).replace(/\/$/, '')
    const response = await event.fetch(`${backendBaseUrl}/api/auth/bootstrap/`, { headers })
    if (!response.ok) return null
    const payload = await response.json()
    if (!payload?.user || !payload?.settings) return null
    return {
      user: payload.user,
      settings: payload.settings,
    } as AuthBootstrap
  } catch (error) {
    console.error('Failed to load auth bootstrap before SSR:', error)
    return null
  }
}

const appendVary = (headers: Headers, value: string) => {
  const values = new Set(
    (headers.get('Vary') || '')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
  )
  values.add(value)
  headers.set('Vary', Array.from(values).join(', '))
}

export const resolvePreferredLanguage = (
  acceptLanguage: string | null,
  authBootstrap: AuthBootstrap | null
): PostLanguageCode =>
  (authBootstrap?.settings.interface_language_manual
    ? normalizeInterfaceLanguage(authBootstrap.settings.interface_language)
    : null) ||
  languageFromAcceptLanguage(acceptLanguage) ||
  originalPostLanguage

export const handleFetch: HandleFetch = async ({ event, request, fetch }) => {
  const upstream = new SearchBackendProxy(process.env.INTERNAL_BACKEND_URL).resolve(request, event.url.origin)
  const response = await fetch(upstream)
  if (new URL(request.url).pathname.startsWith('/api/') && response.headers.get('cache-control')?.includes('no-store')) {
    event.locals.noStore = true
  }
  return response
}

export const handle: Handle = async ({ event, resolve }) => {
  const authBootstrap = await loadAuthBootstrap(event)
  event.locals.authBootstrap = authBootstrap
  const preferredLanguage = resolvePreferredLanguage(
    event.request.headers.get('Accept-Language'),
    authBootstrap
  )
  event.locals.preferredLanguage = preferredLanguage
  const language = languageFromPathname(event.url.pathname) || preferredLanguage
  const isPostDetail = /^\/(?:[a-z]{2}\/)?b\/post\//.test(event.url.pathname)
  const response = await runWithRequestTranslations(language, () =>
    resolve(event, {
      // Svelte owns the SSR head nodes between its hydration markers.
      // Moving individual tags leaves them behind when the route changes.
      transformPageChunk: ({ html }) => localizeAppShellHead(html, language),
    })
  )
  const headers = new Headers(response.headers)
  for (const [name, value] of Object.entries(securityHeaders)) {
    headers.set(name, value)
  }
  if (
    isPostDetail &&
    response.headers.get('content-type')?.includes('text/html')
  ) {
    headers.delete('link')
    headers.set('content-type', 'text/html; charset=utf-8')
  }
  headers.set('Content-Language', postLanguageLocales[language])
  appendVary(headers, 'Accept-Language')
  if (authBootstrap || event.locals.noStore) {
    headers.set('Cache-Control', 'private, no-store, max-age=0')
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  })
}
