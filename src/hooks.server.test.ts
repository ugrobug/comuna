import { describe, expect, it } from 'vitest'
import { prioritizePreviewHeadTags } from './hooks.server'

describe('prioritizePreviewHeadTags', () => {
  it('keeps the full SSR document and moves preview metadata before stylesheets', () => {
    const html = `<!doctype html><html><head>
      <title>Post title - Tambur</title>
      <link rel="stylesheet" href="/app.css">
      <meta name="description" content="Short post preview">
      <meta property="og:title" content="Post title">
      <meta property="og:description" content="Short post preview">
      <meta property="og:image" content="https://tambur.pub/api/posts/42/social-image.jpg">
      <meta name="twitter:card" content="summary_large_image">
    </head><body><div>Application shell</div></body></html>`

    const prioritizedHtml = prioritizePreviewHeadTags(html)

    expect(prioritizedHtml).toContain('<meta property="og:title" content="Post title">')
    expect(prioritizedHtml).toContain(
      '<meta property="og:description" content="Short post preview">'
    )
    expect(prioritizedHtml).toContain(
      '<meta property="og:image" content="https://tambur.pub/api/posts/42/social-image.jpg">'
    )
    expect(prioritizedHtml).toContain('<meta name="twitter:card" content="summary_large_image">')
    expect(prioritizedHtml).toContain('<div>Application shell</div>')
    expect(prioritizedHtml.indexOf('property="og:title"')).toBeLessThan(
      prioritizedHtml.indexOf('rel="stylesheet"')
    )
  })
})
