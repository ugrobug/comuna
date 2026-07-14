import { buildComunMapUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

export const ssr = false

export const load = async ({ fetch, parent, url }) => {
  const parentData = await parent()
  const comun = parentData.comun ?? null
  if (!comun?.slug) {
    throw error(404, 'site.errors.communityNotFound')
  }

  if (!comun?.community_map_enabled && !comun?.can_moderate) {
    throw error(404, 'Карта не включена')
  }

  const response = await fetch(new URL(buildComunMapUrl(comun.slug), url.origin).toString())
  if (!response.ok) {
    throw error(response.status, 'Не удалось загрузить карту')
  }

  const payload = await response.json().catch(() => ({}))
  return {
    comun: payload?.comun ?? comun,
    points: Array.isArray(payload?.points) ? payload.points : [],
  }
}
