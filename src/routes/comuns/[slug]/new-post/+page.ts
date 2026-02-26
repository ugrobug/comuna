import { buildComunUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

export const load = async ({ fetch, params, url }) => {
  const response = await fetch(new URL(buildComunUrl(params.slug), url.origin).toString())
  if (!response.ok) {
    if (response.status === 404) {
      throw error(404, 'Комуна не найдена')
    }
    throw error(response.status, 'Не удалось загрузить коммуну')
  }

  const payload = await response.json()
  return {
    comun: payload?.comun ?? null,
  }
}

