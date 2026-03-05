import { buildAuthorPostsUrl } from '$lib/api/backend'
import { error, redirect } from '@sveltejs/kit'

const PAGE_SIZE = 10

export const load = async ({ params, fetch, url }) => {
  const username = params.username
  const requestUrl = new URL(buildAuthorPostsUrl(username), url.origin)
  requestUrl.searchParams.set('limit', String(PAGE_SIZE))

  const response = await fetch(requestUrl.toString())
  if (!response.ok) {
    if (response.status === 404) {
      throw error(404, 'Автор не найден')
    }
    throw error(response.status, 'Не удалось загрузить посты')
  }

  const data = await response.json()
  const siteUserId = Number(data?.author?.site_user_id ?? 0)
  if (Number.isFinite(siteUserId) && siteUserId > 0) {
    throw redirect(301, `/id${siteUserId}`)
  }

  return {
    author: data.author,
    posts: data.posts ?? [],
  }
}
