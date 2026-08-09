export const VK_VIDEO_URL_PATTERN =
  /^\s*https?:\/\/(?:(?:www|m)\.)?(?:vk\.com|vkvideo\.ru)\/(?:(?:video|clip)(-?\d+)_(\d+)|[^?#\s]*\?(?:[^#\s]*&)?z=(?:video|clip)(-?\d+)_(\d+))(?:[/?#&%][^\s]*)?\s*$/i

export interface VkVideoId {
  ownerId: string
  videoId: string
}

export const vkVideoIdFromMatchGroups = (
  groups: Array<string | undefined>
): VkVideoId | null => {
  const [directOwnerId, directVideoId, queryOwnerId, queryVideoId] = groups
  const ownerId = directOwnerId || queryOwnerId
  const videoId = directVideoId || queryVideoId

  if (!ownerId || !videoId) return null
  return { ownerId, videoId }
}

export const extractVkVideoId = (url?: string): VkVideoId | null => {
  if (!url) return null
  const match = url.match(VK_VIDEO_URL_PATTERN)
  return match ? vkVideoIdFromMatchGroups(match.slice(1)) : null
}

export const vkVideoEmbedUrlFromMatchGroups = (
  groups: Array<string | undefined>
): string => {
  const video = vkVideoIdFromMatchGroups(groups)
  if (!video) return ''

  const params = new URLSearchParams({
    oid: video.ownerId,
    id: video.videoId,
  })
  return `https://vk.com/video_ext.php?${params.toString()}`
}
