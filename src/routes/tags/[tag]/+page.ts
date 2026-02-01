import { buildTagPostsUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

const PAGE_SIZE = 10

export const load = async ({ params, fetch, url }) => {
  const tag = params.tag
  const requestUrl = new URL(buildTagPostsUrl(tag), url.origin)
  requestUrl.searchParams.set('limit', String(PAGE_SIZE))

  const response = await fetch(requestUrl.toString())
  if (!response.ok) {
    if (response.status === 404) {
      throw error(404, 'Тег не найден')
    }
    throw error(response.status, 'Не удалось загрузить посты')
  }

  const data = await response.json()

  return {
    tag: data.tag ?? { name: tag },
    posts: data.posts ?? [],
  }
}
