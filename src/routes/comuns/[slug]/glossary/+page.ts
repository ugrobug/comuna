import { buildComunUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

export const load = async ({ fetch, params, url }) => {
  const slug = params.slug
  const comunResponse = await fetch(new URL(buildComunUrl(slug), url.origin).toString())
  if (!comunResponse.ok) {
    if (comunResponse.status === 404) {
      throw error(404, 'Сообщество не найдено')
    }
    throw error(comunResponse.status, 'Не удалось загрузить сообщество')
  }
  const comunPayload = await comunResponse.json()
  const comun = comunPayload?.comun ?? null
  if (!comun?.glossary_enabled) {
    throw error(404, 'Глоссарий не включен')
  }
  return {
    comun,
  }
}
