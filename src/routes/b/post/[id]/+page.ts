import { buildPostDetailUrl } from '$lib/api/backend'
import { slugifyTitle } from '$lib/util/slug'
import { error, redirect } from '@sveltejs/kit'

export const load = async ({ params, fetch }) => {
  const rawId = params.id
  const id = Number(rawId.split('-')[0])
  if (!Number.isInteger(id)) {
    throw error(404, 'Пост не найден')
  }

  const response = await fetch(buildPostDetailUrl(id))
  if (!response.ok) {
    throw error(response.status, 'Пост не найден')
  }

  const data = await response.json()

  const slug = slugifyTitle(data.post?.title ?? '')
  const canonicalId = slug ? `${id}-${slug}` : `${id}`
  if (rawId !== canonicalId) {
    throw redirect(301, `/b/post/${canonicalId}`)
  }

  return {
    post: data.post,
  }
}
