import { buildComunPostsUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

const PAGE_SIZE = 10

export const load = async ({ fetch, params, url, parent }) => {
  const slug = params.slug
  const category = url.searchParams.get('category') || ''
  const hasCategoriesFilter = url.searchParams.has('categories')
  const categorySlugs = hasCategoriesFilter
    ? (url.searchParams.get('categories') || '')
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean)
    : category
      ? [category]
      : []
  const parentData = await parent()
  const language = parentData.language ?? 'ru'

  const postsUrl = new URL(
    buildComunPostsUrl(
      slug,
      hasCategoriesFilter
        ? { categorySlugs, language }
        : { categorySlug: category || undefined, language }
    ),
    url.origin
  )
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
    selectedCategorySlugs: Array.isArray(postsPayload?.selected_category_slugs)
      ? postsPayload.selected_category_slugs
      : categorySlugs,
    categoryFilterExplicit: Boolean(
      postsPayload?.category_filter_explicit ?? (hasCategoriesFilter || Boolean(category))
    ),
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
