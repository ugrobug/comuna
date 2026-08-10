import { buildComunRoadmapUrl } from '$lib/api/backend'
import { languageFromPathname, originalPostLanguage } from '$lib/postLanguages'
import { error } from '@sveltejs/kit'

export const load = async ({ fetch, params, url }) => {
  const language = languageFromPathname(url.pathname) ?? originalPostLanguage
  const response = await fetch(
    new URL(buildComunRoadmapUrl(params.slug, { language }), url.origin).toString()
  )
  const payload = await response.json().catch(() => ({}))

  if (!response.ok) {
    if (response.status === 404) {
      throw error(404, 'site.errors.communityNotFound')
    }
    throw error(response.status, payload?.error || 'Failed to load roadmap')
  }

  return {
    comun: payload?.comun ?? null,
    items: Array.isArray(payload?.items) ? payload.items : [],
    language,
  }
}
