import { buildComunRoadmapUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

export const load = async ({ fetch, params, parent }) => {
  const parentData = await parent()
  const comun = parentData.comun ?? null
  const language = parentData.language ?? 'ru'
  if (comun && comun.roadmap_enabled === false) {
    throw error(404, 'Дорожная карта отключена')
  }

  const response = await fetch(buildComunRoadmapUrl(params.slug, { language }))
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    if (response.status === 404) {
      throw error(404, 'site.errors.communityNotFound')
    }
    throw error(response.status, payload?.error || 'Не удалось загрузить дорожную карту')
  }

  return {
    comun: payload?.comun ?? comun,
    items: Array.isArray(payload?.items) ? payload.items : [],
    language,
  }
}
