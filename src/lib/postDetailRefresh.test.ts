import { describe, expect, it } from 'vitest'
import { mergePostDetailPersonalization } from './postDetailRefresh'

describe('mergePostDetailPersonalization', () => {
  const serverPost = {
    id: 21960,
    title: 'Партизанская реклама ресторана',
    content: 'serialized-full-content',
    original_content: 'serialized-full-content',
    tags: [{ name: 'реклама' }],
    is_favorite: false,
    user_vote: 0,
    author: { username: 'author', can_manage: false },
    comun: { slug: 'marketing', is_subscribed: false, subscribers_count: 1 },
  }

  it('does not replace static post content with an authenticated response', () => {
    const refreshed = mergePostDetailPersonalization(serverPost, {
      ...serverPost,
      content: '',
      original_content: '',
      tags: [],
      is_favorite: true,
      user_vote: 1,
    })

    expect(refreshed.content).toBe(serverPost.content)
    expect(refreshed.original_content).toBe(serverPost.original_content)
    expect(refreshed.tags).toBe(serverPost.tags)
    expect(refreshed.is_favorite).toBe(true)
    expect(refreshed.user_vote).toBe(1)
  })

  it('keeps the existing object when personalization has not changed', () => {
    const refreshed = mergePostDetailPersonalization(serverPost, { ...serverPost })

    expect(refreshed).toBe(serverPost)
  })

  it('merges nested permission fields without replacing community data', () => {
    const refreshed = mergePostDetailPersonalization(serverPost, {
      comun: { slug: 'marketing', can_moderate: true },
      author: { username: 'author', can_manage: true },
    })

    expect(refreshed.comun).toEqual({
      slug: 'marketing',
      is_subscribed: false,
      subscribers_count: 1,
      can_moderate: true,
    })
    expect(refreshed.author).toEqual({ username: 'author', can_manage: true })
  })
})
