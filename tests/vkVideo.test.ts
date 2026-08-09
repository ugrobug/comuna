import { describe, expect, it } from 'vitest'
import {
  extractVkVideoId,
  VK_VIDEO_URL_PATTERN,
  vkVideoEmbedUrlFromMatchGroups,
} from '../src/lib/vkVideo'

const expected = { ownerId: '-211232966', videoId: '456241404' }

describe('VK video URL parsing', () => {
  it.each([
    'https://vkvideo.ru/video-211232966_456241404',
    'https://vkvideo.ru/video-211232966_456241404?list=example',
    'https://vk.com/video-211232966_456241404',
    'https://m.vk.com/video-211232966_456241404?from=video',
    'https://vk.com/video?z=video-211232966_456241404%2Fpl_cat_updates',
    'https://vk.com/videos-211232966?z=video-211232966_456241404%2Fclub211232966',
    'https://vk.com/@channel?from=search&z=video-211232966_456241404',
    'https://vkvideo.ru/@channel?z=video-211232966_456241404',
  ])('extracts the owner and video ids from %s', (url) => {
    expect(extractVkVideoId(url)).toEqual(expected)
  })

  it('supports videos owned by a user', () => {
    expect(extractVkVideoId('https://vk.com/video12345_67890')).toEqual({
      ownerId: '12345',
      videoId: '67890',
    })
  })

  it('supports VK clips', () => {
    expect(extractVkVideoId('https://vk.com/clip-211232966_456241404')).toEqual(
      expected
    )
  })

  it('builds the EditorJS iframe URL from regex groups', () => {
    const match = 'https://vkvideo.ru/video-211232966_456241404'.match(
      VK_VIDEO_URL_PATTERN
    )

    expect(match).not.toBeNull()
    expect(vkVideoEmbedUrlFromMatchGroups(match?.slice(1) || [])).toBe(
      'https://vk.com/video_ext.php?oid=-211232966&id=456241404'
    )
  })

  it.each([
    'https://vk.com/',
    'https://vk.com/wall-211232966_456241404',
    'https://example.com/video-211232966_456241404',
    'some text https://vk.com/video-211232966_456241404',
  ])('does not treat non-video input as a VK video: %s', (url) => {
    expect(extractVkVideoId(url)).toBeNull()
  })
})
