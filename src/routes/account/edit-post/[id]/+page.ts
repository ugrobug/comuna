import { error } from '@sveltejs/kit'

export const load = async ({ params }) => {
  const postId = Number(params.id)
  if (!Number.isFinite(postId) || postId <= 0) {
    throw error(404, 'site.errors.postNotFound')
  }

  return {
    postId,
  }
}
