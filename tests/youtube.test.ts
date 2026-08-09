import { describe, expect, it } from 'vitest'
import {
  extractYouTubeVideoId,
  matchYouTubeUrl,
  youtubeVideoIdFromMatchGroups,
} from '../src/lib/youtube'

const videoId = 'dQw4w9WgXcQ'

describe('YouTube URL parsing', () => {
  it.each([
    `https://www.youtube.com/watch?v=${videoId}`,
    `https://www.youtube.com/watch?si=share-token&v=${videoId}&feature=youtu.be`,
    `https://m.youtube.com/watch?v=${videoId}&t=42s`,
    `https://music.youtube.com/watch?v=${videoId}&list=example`,
    `https://youtu.be/${videoId}?si=share-token`,
    `https://youtube.com/shorts/${videoId}`,
    `https://youtube.com/live/${videoId}?feature=share`,
    `https://www.youtube-nocookie.com/embed/${videoId}`,
  ])('extracts the video id from %s', (url) => {
    expect(extractYouTubeVideoId(url)).toBe(videoId)
  })

  it('uses the same match groups as the EditorJS embed service', () => {
    const match = matchYouTubeUrl(
      `https://www.youtube.com/watch?feature=shared&v=${videoId}`
    )

    expect(match).not.toBeNull()
    expect(youtubeVideoIdFromMatchGroups(match?.slice(1) || [])).toBe(videoId)
  })

  it.each([
    'https://www.youtube.com/',
    'https://www.youtube.com/watch?v=too-short',
    'https://example.com/watch?v=dQw4w9WgXcQ',
    'some text https://youtu.be/dQw4w9WgXcQ',
  ])('does not treat non-video input as a YouTube video: %s', (url) => {
    expect(extractYouTubeVideoId(url)).toBeNull()
  })
})
