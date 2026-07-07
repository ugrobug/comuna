import { buildComunUrl } from '$lib/api/backend'
import { languageFromPathname, originalPostLanguage } from '$lib/postLanguages'
import { error } from '@sveltejs/kit'

export const load = async ({ fetch, params, url, depends }) => {
  const slug = params.slug
  const language = languageFromPathname(url.pathname) ?? originalPostLanguage
  depends(`app:comun:${slug}`)

  const comunResponse = await fetch(
    new URL(buildComunUrl(slug, { language }), url.origin).toString()
  )
  if (!comunResponse.ok) {
    if (comunResponse.status === 404) {
      throw error(404, 'site.errors.communityNotFound')
    }
    throw error(comunResponse.status, 'Не удалось загрузить сообщество')
  }

  const comunPayload = await comunResponse.json()

  return {
    slug,
    language,
    comun: comunPayload?.comun ?? null,
  }
}
