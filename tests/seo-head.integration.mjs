// ADAPTER=node npm run build && node --test --test-force-exit tests/seo-head.integration.mjs
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
import { Server } from '../.svelte-kit/output/server/index.js'
import { manifest } from '../.svelte-kit/output/server/manifest.js'

const origin = 'https://frontend.test'
const languages = ['ru', 'en', 'es', 'pt', 'de', 'fr', 'tr', 'id']
const versions = languages.map(language => ({
  language,
  hreflang: language,
  path: (language === 'ru' ? '' : '/' + language) + '/b/post/42-fixture',
}))
const comun = { id: 1, slug: 'fixture', name: 'Fixture Club', seo_indexable: true, categories: [] }
const user = { id: 25, username: 'fixture-author', title: 'Fixture Author' }

function fixture(url) {
  switch (url.pathname) {
    case '/api/posts/42/': {
      const language = url.searchParams.get('lang') || 'ru'
      return { post: {
        id: 42, title: 'Fixture', content: '<p>&quot;Cinema&quot; &amp; music.</p>',
        author: user, comun, created_at: '2026-01-01T00:00:00Z',
        original_language: 'ru', language, language_versions: versions,
        seo_indexable: language !== 'es', social_image_url: origin + '/preview.jpg',
      } }
    }
    case '/api/comuns/fixture/': return { comun }
    case '/api/comuns/fixture/posts/': return { posts: [], has_more: false }
    case '/api/site-users/25/profile/': return { user, posts: [], comuns: [] }
    default: return {}
  }
}

test('render the route’s own metadata for articles, communities, profiles and static pages', async t => {
  const backend = 'https://backend.test'
  const originalBackend = process.env.INTERNAL_BACKEND_URL
  process.env.INTERNAL_BACKEND_URL = backend
  t.after(() => {
    if (originalBackend === undefined) delete process.env.INTERNAL_BACKEND_URL
    else process.env.INTERNAL_BACKEND_URL = originalBackend
  })
  t.mock.method(globalThis, 'fetch', async request => {
    const url = new URL(request.url ?? request)
    assert.equal(url.origin, backend)
    return Response.json(fixture(url), { headers: { 'access-control-allow-origin': origin } })
  })
  const server = new Server(manifest)
  await server.init({ env: { PUBLIC_SITE_URL: origin } })
  for (const path of [...versions.slice(0, 3).map(v => v.path), '/comuns/fixture', '/id25', '/about']) {
    await t.test(path, async () => {
      const response = await server.respond(new Request(origin + path), { getClientAddress: () => '127.0.0.1' })
      assert.equal(response.status, 200)
      const html = await response.text()
      const dom = new JSDOM(html)
      try {
        const head = dom.window.document.head
        const values = (selector, attribute) => Array.from(head.querySelectorAll(selector), tag => tag.getAttribute(attribute))
        assert.deepEqual(values('link[rel=canonical]', 'href'), [origin + path])
        const descriptions = values('meta[name=description]', 'content')
        assert.equal(descriptions.length, 1)
        assert.ok(descriptions[0]?.trim())
        const articles = Array.from(head.querySelectorAll('script[type="application/ld+json"]'), tag => JSON.parse(tag.textContent))
          .filter(schema => schema['@type'] === 'BlogPosting')
        if (path.includes('/b/post/')) {
          assert.deepEqual(descriptions, ['"Cinema" & music.'])
          assert.deepEqual(values('meta[property="og:description"]', 'content'), descriptions)
          assert.deepEqual(values('meta[name="twitter:description"]', 'content'), descriptions)
          assert.deepEqual(values('meta[name=robots]', 'content'), [path.startsWith('/es/') ? 'noindex, follow' : 'max-image-preview:large'])
          assert.deepEqual(values('link[hreflang]', 'hreflang'), [...languages, 'x-default'])
          assert.deepEqual(values('link[hreflang]', 'href'), [...versions, versions[0]].map(v => origin + v.path))
          assert.deepEqual(articles.map(a => [a.url, a.description]), [[origin + path, descriptions[0]]])
          const preview = html.indexOf('property="og:image"')
          assert.ok(preview >= 0 && preview < html.indexOf('rel="stylesheet"'))
        } else {
          assert.deepEqual(articles, [])
          assert.deepEqual(values('meta[name=robots]', 'content'), path.startsWith('/comuns/') ? ['max-image-preview:large'] : [])
        }
      } finally {
        dom.window.close()
      }
    })
  }
})
