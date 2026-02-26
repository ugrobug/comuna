import { buildComunPostsUrl, buildComunUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

const PAGE_SIZE = 10

export const load = async ({ fetch, params, url }) => {
  const slug = params.slug
  const category = url.searchParams.get('category') || ''

  const comunResponse = await fetch(new URL(buildComunUrl(slug), url.origin).toString())
  if (!comunResponse.ok) {
    if (comunResponse.status === 404) {
      throw error(404, 'Комуна не найдена')
    }
    throw error(comunResponse.status, 'Не удалось загрузить коммуну')
  }
  const comunPayload = await comunResponse.json()

  const postsUrl = new URL(buildComunPostsUrl(slug, { categorySlug: category || undefined }), url.origin)
  postsUrl.searchParams.set('limit', String(PAGE_SIZE))
  const postsResponse = await fetch(postsUrl.toString())
  if (!postsResponse.ok) {
    if (postsResponse.status === 404) {
      throw error(404, 'Комуна не найдена')
    }
    throw error(postsResponse.status, 'Не удалось загрузить посты комуны')
  }
  const postsPayload = await postsResponse.json()

  return {
    comun: comunPayload?.comun ?? postsPayload?.comun ?? null,
    posts: postsPayload?.posts ?? [],
    selectedCategory: postsPayload?.selected_category ?? null,
    categoryCounts: postsPayload?.category_counts ?? [],
    totalCount:
      typeof postsPayload?.total_count === 'number' ? Number(postsPayload.total_count) : null,
    uncategorizedCount:
      typeof postsPayload?.uncategorized_count === 'number'
        ? Number(postsPayload.uncategorized_count)
        : 0,
    pageSize: PAGE_SIZE,
    initialCategorySlug: category || '',
  }
}
