import { buildAuthorPostsUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

export const load = async ({ params, fetch }) => {
  const username = params.username
  const url = buildAuthorPostsUrl(username)

  const response = await fetch(url)
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
