import { buildRubricPostsUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

const PAGE_SIZE = 10

export const load = async ({ params, fetch }) => {
  const slug = params.slug
  const url = new URL(buildRubricPostsUrl(slug))
  url.searchParams.set('limit', String(PAGE_SIZE))

  const response = await fetch(url.toString())
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
