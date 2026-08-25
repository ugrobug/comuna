import { describe, expect, it } from 'vitest'
import { findDzenUrl, isDzenUrl } from './dzen'

describe('Dzen URL detection', () => {
  it('recognizes current and legacy Dzen addresses', () => {
    expect(isDzenUrl('https://dzen.ru/a/example')).toBe(true)
    expect(isDzenUrl('https://zen.yandex.ru/media/example/article')).toBe(true)
    expect(isDzenUrl('https://yandex.ru/zen/article/example')).toBe(true)
  })

  it('does not intercept unrelated Yandex links', () => {
    expect(isDzenUrl('https://yandex.ru/search/?text=tambur')).toBe(false)
    expect(isDzenUrl('https://music.yandex.ru/album/42')).toBe(false)
  })

  it('finds a Dzen link inside copied text and excludes punctuation', () => {
    expect(findDzenUrl('Статья: https://dzen.ru/a/example.')).toEqual({
      href: 'https://dzen.ru/a/example',
      source: 'https://dzen.ru/a/example',
    })
  })
})
