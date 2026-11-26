import { describe, expect, it } from 'vitest'
import { PostMetaDescription } from './PostMetaDescription'

describe('post metadata', () => {
  it('decodes entity references once before truncation and HTML attribute rendering', () => {
    expect(PostMetaDescription.fromContent('<p>&quot;A&quot; &amp; B&#x2014;C&nbsp; D &amp;lt;</p>'))
      .toBe('"A" & B—C D &lt;')
    expect(PostMetaDescription.fromContent('x'.repeat(199) + '&quot;y')).toBe('x'.repeat(199) + '"…')
  })

  it('prefers editorial metadata and supports stored base64 articles', () => {
    const content = { additional: { metaDescription: '&laquo;A&raquo;' }, blocks: [{ type: 'paragraph', data: { text: 'B' } }] }
    expect(PostMetaDescription.fromContent(Buffer.from(JSON.stringify(content)).toString('base64'))).toBe('«A»')
  })

  it('uses the first nonempty paragraph or header, and never exposes raw editor data', () => {
    const blocks = [{ type: 'image' }, { type: 'paragraph', data: { text: '<br>' } }, { type: 'header', data: { text: 'A &amp; B' } }]
    expect(PostMetaDescription.fromContent(JSON.stringify({ blocks }))).toBe('A & B')
    expect(PostMetaDescription.fromContent('{"blocks":[]}')).toBe('')
  })
})
