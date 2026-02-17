import { buildPostDetailUrl } from '$lib/api/backend'
import { slugifyTitle } from '$lib/util/slug'
import { error } from '@sveltejs/kit'

export const ssr = true

export const load = async ({ params, fetch }) => {
  const rawId = params.id
  const id = Number(rawId.split('-')[0])
  if (!Number.isInteger(id) || id <= 0) {
    throw error(404, 'Пост не найден')
  }

  const response = await fetch(buildPostDetailUrl(id))
  if (!response.ok) {
    throw error(response.status, 'Пост не найден')
  }

  const data = await response.json()

  const slug = slugifyTitle(data.post?.title ?? '')
  const canonicalId = slug ? `${id}-${slug}` : `${id}`

  return {
    post: data.post,
    canonicalId,
  }
}
