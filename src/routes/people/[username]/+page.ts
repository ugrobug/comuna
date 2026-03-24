import { buildCommentPersonaProfileUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

const PAGE_SIZE = 20

export const load = async ({ params, fetch, url }) => {
  const requestUrl = new URL(
    buildCommentPersonaProfileUrl(params.username, { limit: PAGE_SIZE, offset: 0 }),
    url.origin
  )

  const response = await fetch(requestUrl.toString())
  if (!response.ok) {
    if (response.status === 404) {
      throw error(404, 'Профиль не найден')
    }
    throw error(response.status, 'Не удалось загрузить профиль')
  }

  const payload = await response.json()

  return {
    pageSize: PAGE_SIZE,
    persona: payload?.persona ?? null,
    comments: payload?.comments ?? [],
    totalComments: payload?.total_comments ?? 0,
  }
}
