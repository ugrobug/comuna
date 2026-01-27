import { buildRubricPostsUrl } from '$lib/api/backend'

const PAGE_SIZE = 10
const COMUNA_SLUG = 'comuna'

export const load = async ({ fetch, url }) => {
  const requestUrl = new URL(buildRubricPostsUrl(COMUNA_SLUG), url.origin)
  requestUrl.searchParams.set('limit', String(PAGE_SIZE))

  const response = await fetch(requestUrl.toString())
  if (!response.ok) {
    return {
      posts: [],
    }
  }

  const data = await response.json()

  return {
    posts: data.posts ?? [],
  }
}
