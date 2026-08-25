import { describe, expect, it } from 'vitest'
import type { BackendPost } from './api/backend'
import type { Settings } from './settings'
import {
  clearHiddenContentReasons,
  getBackendPostHiddenReasons,
  shouldHidePostContent,
} from './postVisibility'

describe('shouldHidePostContent', () => {
  it('keeps hidden-tag posts out of feeds', () => {
    expect(shouldHidePostContent('hide', false)).toBe(true)
  })

  it('lets the full-post component render after the route-level warning is confirmed', () => {
    expect(shouldHidePostContent('hide', true)).toBe(false)
  })

  it('does not treat blur as hidden', () => {
    expect(shouldHidePostContent('blur', false)).toBe(false)
  })
})

describe('hidden content reasons', () => {
  const post = {
    id: 42,
    title: 'Hidden post',
    content: 'Body',
    created_at: '2026-08-24T00:00:00Z',
    author: { username: 'HiddenAuthor' },
    comun: { id: 7, name: 'Hidden community', slug: 'hidden-community' },
    tags: [{ name: 'Space Travel', lemma: 'space-travel' }],
  } as BackendPost

  it('finds every rule that hides a directly opened post', () => {
    const settings = {
      hiddenPostIds: [42],
      hiddenAuthors: ['hiddenauthor'],
      hiddenComuns: ['hidden-community'],
      tagRules: { 'space-travel': 'hide' as const },
    } as Settings

    expect(getBackendPostHiddenReasons(post, settings).map((reason) => reason.kind)).toEqual([
      'post',
      'author',
      'community',
      'tag',
    ])
  })

  it('removes all matching rules when content is restored permanently', () => {
    const settings = {
      hiddenPostIds: [7, 42],
      hiddenAuthors: ['another', 'hiddenauthor'],
      hiddenComuns: ['hidden-community', 'another-community'],
      tagRules: { 'space-travel': 'hide' as const, keep: 'hide' as const },
    } as Settings
    const reasons = getBackendPostHiddenReasons(post, settings)
    const next = clearHiddenContentReasons(settings, reasons)

    expect(next.hiddenPostIds).toEqual([7])
    expect(next.hiddenAuthors).toEqual(['another'])
    expect(next.hiddenComuns).toEqual(['another-community'])
    expect(next.tagRules['space-travel']).toBeUndefined()
    expect(next.tagRules.keep).toBe('hide')
  })
})
