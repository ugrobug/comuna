import { describe, expect, it } from 'vitest'
import { sanitizePostHtml } from '../src/lib/security/html'

describe('post HTML sanitizer', () => {
  it('keeps draft review block identifiers and strips event handlers', () => {
    const sanitized = sanitizePostHtml(`
      <div class="draft-review-block" data-draft-block-id="intro-block">
        <button
          type="button"
          data-draft-comment-button="intro-block"
          aria-label="Comment"
          onclick="alert(1)"
        ></button>
      </div>
    `)

    expect(sanitized).toContain('data-draft-block-id="intro-block"')
    expect(sanitized).toContain('data-draft-comment-button="intro-block"')
    expect(sanitized).not.toContain('onclick')
  })
})
