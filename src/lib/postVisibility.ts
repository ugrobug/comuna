import type { BackendPost } from '$lib/api/backend'
import type { Settings } from '$lib/settings'

export const isBackendPostVisible = (
  post: BackendPost,
  settings: Pick<Settings, 'hiddenAuthors' | 'hiddenPostIds' | 'hiddenComuns'>
): boolean => {
  if ((settings.hiddenPostIds ?? []).includes(post.id)) return false

  const author = (post.author?.username ?? '').trim().toLowerCase()
  if (author && (settings.hiddenAuthors ?? []).some((value) => value.trim().toLowerCase() === author)) {
    return false
  }

  const comun = (post.comun?.slug ?? post.comun_slug ?? '').trim().toLowerCase()
  if (comun && (settings.hiddenComuns ?? []).some((value) => value.trim().toLowerCase() === comun)) {
    return false
  }

  return true
}
