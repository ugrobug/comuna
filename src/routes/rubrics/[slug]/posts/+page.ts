import { buildRubricPostsUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

export const load = async ({ params, fetch }) => {
  const slug = params.slug
  const url = buildRubricPostsUrl(slug)

  const response = await fetch(url)
  if (!response.ok) {
    if (response.status === 404) {
      throw error(404, 'Рубрика не найдена')
    }
    throw error(response.status, 'Не удалось загрузить посты')
  }

  const data = await response.json()

  return {
    rubric: data.rubric,
    posts: data.posts ?? [],
  }
}
