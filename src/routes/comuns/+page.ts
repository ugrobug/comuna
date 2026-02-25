import { buildComunsUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

export const load = async ({ fetch, url }) => {
  const response = await fetch(new URL(buildComunsUrl(), url.origin).toString())
  if (!response.ok) {
    throw error(response.status, 'Не удалось загрузить комуны')
  }
  const data = await response.json()
  return {
    comuns: data?.comuns ?? [],
  }
}

