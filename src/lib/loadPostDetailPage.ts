import { buildPostDetailUrl } from '$lib/api/backend'
import { buildLocalizedPostPath, normalizePostLanguage } from '$lib/postLanguages'
import { slugifyTitle } from '$lib/util/slug'
import { error, redirect } from '@sveltejs/kit'

export const loadPostDetailPage = async ({ params, fetch }) => {
  const rawId = params.id
  const id = Number(rawId.split('-')[0])
  if (!Number.isInteger(id) || id <= 0) {
    throw error(404, 'site.errors.postNotFound')
  }

  const language = normalizePostLanguage(params.lang)
  const response = await fetch(buildPostDetailUrl(id, language))
  if (!response.ok) {
    let payload: { redirect_url?: string } = {}
    try {
      payload = await response.json()
    } catch {
      payload = {}
    }
    if (payload.redirect_url) {
      throw redirect(302, payload.redirect_url)
    }
    throw error(response.status, 'site.errors.postNotFound')
  }

  const data = await response.json()
  const languageVersions = Array.isArray(data.post?.language_versions)
    ? data.post.language_versions
    : []
  if (data.post?.translation_unavailable && data.post?.original_language !== language) {
    const originalVersion = languageVersions.find(
      (version) => version?.language === data.post?.original_language
    )
    if (originalVersion?.path) {
      throw redirect(302, originalVersion.path)
    }
  }
  const currentVersion = languageVersions.find((version) => version?.language === language)
  const slug = slugifyTitle(data.post?.title ?? '')
  const canonicalId = slug ? `${id}-${slug}` : `${id}`
  const canonicalPath = currentVersion?.path || buildLocalizedPostPath(canonicalId, language)

  return {
    post: data.post,
    language,
    languageVersions,
    canonicalId,
    canonicalPath,
  }
}
