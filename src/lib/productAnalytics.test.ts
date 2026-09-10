import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('$app/environment', () => ({ browser: true }))

import {
  isPostPath,
  sanitizeEventParams,
  shouldTrackMeaningfulRead,
  trackProductEvent,
} from './productAnalytics'

describe('product analytics', () => {
  beforeEach(() => {
    window.__TAMBUR_YM_COUNTER_ID__ = 123
    window.ym = vi.fn()
  })

  it('sends a valuable event and the composed North Star goal', () => {
    trackProductEvent('comment_created', { post_id: 42 })
    expect(window.ym).toHaveBeenNthCalledWith(1, 123, 'reachGoal', 'comment_created', {
      post_id: 42,
    })
    expect(window.ym).toHaveBeenNthCalledWith(2, 123, 'reachGoal', 'valuable_action', {
      post_id: 42,
      action: 'comment_created',
    })
  })

  it('does not count unsubscribe as value', () => {
    trackProductEvent('community_unsubscribed', { community: 'books' })
    expect(window.ym).toHaveBeenCalledTimes(1)
  })

  it('recognizes post paths and meaningful engagement threshold', () => {
    expect(isPostPath('/b/post/4492-example')).toBe(true)
    expect(isPostPath('/en/post/example')).toBe(true)
    expect(isPostPath('/comuns/books')).toBe(false)
    expect(shouldTrackMeaningfulRead(60, 0.7)).toBe(true)
    expect(shouldTrackMeaningfulRead(59, 1)).toBe(false)
  })

  it('drops null values and truncates strings', () => {
    expect(sanitizeEventParams({ empty: null, title: 'a'.repeat(220) })).toEqual({
      title: 'a'.repeat(200),
    })
  })
})
