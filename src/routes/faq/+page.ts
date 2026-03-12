import { error } from '@sveltejs/kit'
import { buildRubricPostsUrl } from '$lib/api/backend'

const FAQ_RUBRIC_SLUG = 'faq'
const PAGE_SIZE = 50
const MAX_OFFSET = 5000

export const load = async ({ fetch, url }) => {
  const posts: any[] = []
  let rubric: Record<string, any> | null = null
  let offset = 0

  while (offset <= MAX_OFFSET) {
    const requestUrl = new URL(buildRubricPostsUrl(FAQ_RUBRIC_SLUG), url.origin)
    requestUrl.searchParams.set('limit', String(PAGE_SIZE))
    requestUrl.searchParams.set('offset', String(offset))

    const response = await fetch(requestUrl.toString(), { cache: 'no-store' })
    if (!response.ok) {
      if (response.status === 404) {
        throw error(404, 'FAQ не найден')
      }
      throw error(response.status, 'Не удалось загрузить FAQ')
    }

    const payload = await response.json().catch(() => ({}))
    if (!rubric && payload?.rubric) {
      rubric = payload.rubric
    }

    const chunk = Array.isArray(payload?.posts) ? payload.posts : []
    posts.push(...chunk)

    if (chunk.length < PAGE_SIZE) {
      break
    }

    offset += PAGE_SIZE
  }

  return {
    rubric,
    posts,
  }
}
