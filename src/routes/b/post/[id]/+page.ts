import { buildPostDetailUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

export const load = async ({ params, fetch }) => {
  const id = Number(params.id)
  if (!Number.isInteger(id)) {
    throw error(404, 'Пост не найден')
  }

  const response = await fetch(buildPostDetailUrl(id))
  if (!response.ok) {
    throw error(response.status, 'Пост не найден')
  }

  const data = await response.json()

  return {
    post: data.post,
  }
}
