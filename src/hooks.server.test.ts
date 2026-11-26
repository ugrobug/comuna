import { describe, expect, it } from 'vitest'
import { handle, resolvePreferredLanguage } from './hooks.server'

describe('post SSR head', () => {
  it('preserves route-owned nodes and their hydration boundaries for preview and navigation', async () => {
    const head = '<!--post--><link rel="canonical" href="/es/b/post/42">' +
      '<meta name="robots" content="noindex, follow"><meta property="og:image" content="/42.jpg">' +
      '<!--]--><link rel="stylesheet" href="/app.css">'
    const url = new URL('https://tambur.pub/es/b/post/42')
    const event = { url, request: new Request(url), locals: {} }
    const response = await handle({
      event: event as Parameters<typeof handle>[0]['event'],
      resolve: async (_, options) => {
        const html = '<html lang="ru"><head>' + head + '</head><body></body></html>'
        return new Response(await options?.transformPageChunk?.({ html, done: true }) || html)
      },
    })
    const html = await response.text()
    expect(event.locals).toMatchObject({ preferredLanguage: 'ru' })
    expect(html).toContain('<html lang="es">')
    expect(html).toContain('<head>' + head + '</head>')
  })
})

describe('resolvePreferredLanguage', () => {
  const bootstrap = {
    user: { id: 1 },
    settings: {
      interface_language: 'en',
      interface_language_manual: true,
    },
  } as any

  it('uses a manual user language before the browser language', () => {
    expect(resolvePreferredLanguage('ru-RU,ru;q=0.9', bootstrap)).toBe('en')
  })

  it('uses the request language for guests', () => {
    expect(resolvePreferredLanguage('de-DE', null)).toBe('de')
  })
})
