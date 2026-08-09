const YOUTUBE_VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/

export const YOUTUBE_URL_PATTERN =
  /^\s*(?:https?:\/\/)?(?:(?:(?:www|m|music)\.)?(?:youtube\.com)\/(?:(?:watch\?(?:[^#\s]*&)?v=)([A-Za-z0-9_-]{11})|(?:embed|shorts|live|v)\/([A-Za-z0-9_-]{11}))|(?:www\.)?youtube-nocookie\.com\/embed\/([A-Za-z0-9_-]{11})|youtu\.be\/([A-Za-z0-9_-]{11}))(?:[/?#&][^\s]*)?\s*$/i

export const youtubeVideoIdFromMatchGroups = (
  groups: Array<string | undefined>
): string =>
  groups.find((value) => YOUTUBE_VIDEO_ID_PATTERN.test(value || '')) || ''

export const matchYouTubeUrl = (url?: string): RegExpMatchArray | null => {
  if (!url) return null
  return url.match(YOUTUBE_URL_PATTERN)
}

export const extractYouTubeVideoId = (url?: string): string | null => {
  const match = matchYouTubeUrl(url)
  if (!match) return null
  return youtubeVideoIdFromMatchGroups(match.slice(1)) || null
}
