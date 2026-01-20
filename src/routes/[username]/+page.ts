import { buildAuthorPostsUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

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

  return {
    author: data.author,
    posts: data.posts ?? [],
  }
}
