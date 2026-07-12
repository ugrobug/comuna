import { describe, expect, it } from 'vitest'
import { buildSocialCrawlerHtml } from './hooks.server'

describe('buildSocialCrawlerHtml', () => {
  it('keeps preview metadata and exposes title and description in the body', () => {
    const html = `<!doctype html><html><head>
      <title>Post title - Tambur</title>
      <meta name="description" content="Short post preview">
      <meta property="og:title" content="Post title">
      <meta property="og:description" content="Short post preview">
      <meta property="og:image" content="https://media.tambur.pub/post.webp">
    </head><body><div>Application shell</div></body></html>`

    const crawlerHtml = buildSocialCrawlerHtml(html)

    expect(crawlerHtml).toContain('<meta property="og:title" content="Post title">')
    expect(crawlerHtml).toContain(
      '<meta property="og:description" content="Short post preview">'
    )
    expect(crawlerHtml).toContain('<h1>Post title - Tambur</h1>')
    expect(crawlerHtml).toContain('<p>Short post preview</p>')
    expect(crawlerHtml).not.toContain('og:image')
    expect(crawlerHtml).not.toContain('media.tambur.pub')
    expect(crawlerHtml).not.toContain('<img')
    expect(crawlerHtml).not.toContain('Application shell')
  })
})
