import { describe, expect, it } from 'vitest'
import { PostGallery } from './PostGallery'

describe('body galleries', () => {
  it('preserves original URLs, order and selection through repeated enhancement', () => {
    const root = document.createElement('div')
    root.innerHTML = '<div class="post-gallery"><img src="one-640.webp" srcset="one-640.webp 640w, one-1920.webp 1920w" data-expandable-src="one-1920.webp" alt="One"><img src="two-640.webp" data-expandable-src="two-1920.webp" alt="Two"></div><div class="post-gallery"><img src="other.webp"></div>'
    const first = root.children[0]
    new PostGallery(first).enhance()
    const thumbs = first.querySelectorAll<HTMLImageElement>('.featured-gallery-thumb img')
    expect(Array.from(thumbs, img => img.dataset.expandableSrc)).toEqual(['one-1920.webp', 'two-1920.webp'])
    expect(thumbs[0].sizes).toBe('96px')
    ;(thumbs[1].parentElement as HTMLButtonElement).click()
    expect(first.querySelector('img')?.getAttribute('data-expandable-src')).toBe('two-1920.webp')
    expect(first.querySelector('.active')?.getAttribute('aria-pressed')).toBe('true')
    new PostGallery(first).enhance()
    expect(first.querySelectorAll('img')).toHaveLength(3)
    expect(first.querySelector('img')?.getAttribute('alt')).toBe('Two')
    expect(root.children[1].querySelectorAll('img')).toHaveLength(1)
  })
})
