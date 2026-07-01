import ComunSidebarInfo from '$lib/components/ui/sidebar/ComunSidebarInfo.svelte'
import { buildComunSidebarUrl, buildPostDetailUrl } from '$lib/api/backend'
import { buildLocalizedPostPath, normalizePostLanguage } from '$lib/postLanguages'
import { slugifyTitle } from '$lib/util/slug'
import { error, redirect } from '@sveltejs/kit'

export const loadPostDetailPage = async ({ params, fetch, url }) => {
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
  const comunSlug = data.post?.comun?.slug || data.post?.comun_slug || ''
  let sidebarComun = data.post?.comun ?? null

  if (comunSlug) {
    try {
      const comunResponse = await fetch(new URL(buildComunSidebarUrl(comunSlug), url.origin).toString())
      if (comunResponse.ok) {
        const comunPayload = await comunResponse.json()
        sidebarComun = comunPayload?.comun ?? sidebarComun
      }
    } catch {
      sidebarComun = data.post?.comun ?? null
    }
  }

  const languageVersions = Array.isArray(data.post?.language_versions)
    ? data.post.language_versions
    : []
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
    slots: sidebarComun
      ? {
          sidebar: {
            component: ComunSidebarInfo,
            props: {
              comun: sidebarComun,
            },
          },
        }
      : undefined,
  }
}
