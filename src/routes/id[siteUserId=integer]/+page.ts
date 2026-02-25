import { buildPublicUserProfileUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

const PAGE_SIZE = 10

export const load = async ({ params, fetch, url }) => {
  const siteUserId = params.siteUserId
  const requestUrl = new URL(
    buildPublicUserProfileUrl(siteUserId, { limit: PAGE_SIZE, offset: 0 }),
    url.origin
  )

  const response = await fetch(requestUrl.toString())
  if (!response.ok) {
    if (response.status === 404) {
      throw error(404, 'Пользователь не найден')
    }
    throw error(response.status, 'Не удалось загрузить профиль пользователя')
  }

  const payload = await response.json()

  return {
    pageSize: PAGE_SIZE,
    profile: payload?.user ?? null,
    comuns: payload?.comuns ?? [],
    posts: payload?.posts ?? [],
    totalPosts: payload?.total_posts ?? 0,
  }
}
