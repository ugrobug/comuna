import { buildComunPostsUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

const PAGE_SIZE = 10

export const load = async ({ fetch, params, url, parent }) => {
  const slug = params.slug
  const category = url.searchParams.get('category') || ''
  const parentData = await parent()

  const postsUrl = new URL(buildComunPostsUrl(slug, { categorySlug: category || undefined }), url.origin)
  postsUrl.searchParams.set('limit', String(PAGE_SIZE))
  const postsResponse = await fetch(postsUrl.toString())
  if (!postsResponse.ok) {
    if (postsResponse.status === 404) {
      throw error(404, 'site.errors.communityNotFound')
    }
    throw error(postsResponse.status, 'Не удалось загрузить посты сообщества')
  }
  const postsPayload = await postsResponse.json()

  return {
    comun: parentData.comun ?? postsPayload?.comun ?? null,
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
