import { describe, expect, it } from 'vitest'
import { shouldHidePostContent } from './postVisibility'

describe('shouldHidePostContent', () => {
  it('keeps hidden-tag posts out of feeds', () => {
    expect(shouldHidePostContent('hide', false)).toBe(true)
  })

  it('shows a hidden-tag post when its full page is opened directly', () => {
    expect(shouldHidePostContent('hide', true)).toBe(false)
  })

  it('does not treat blur as hidden', () => {
    expect(shouldHidePostContent('blur', false)).toBe(false)
  })
})
