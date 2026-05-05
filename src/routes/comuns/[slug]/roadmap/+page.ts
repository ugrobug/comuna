import { buildComunPostsUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

const PREVIEW_LIMIT = 12

export const load = async ({ fetch, params, url, parent }) => {
  const slug = params.slug
  const parentData = await parent()
  const comun = parentData.comun ?? null
  if (comun && comun.roadmap_enabled === false) {
    throw error(404, 'Дорожная карта отключена')
  }

  const statsUrl = new URL(buildComunPostsUrl(slug), url.origin)
  statsUrl.searchParams.set('limit', '1')
  const statsResponse = await fetch(statsUrl.toString())
  if (!statsResponse.ok) {
    if (statsResponse.status === 404) {
      throw error(404, 'Сообщество не найдено')
    }
    throw error(statsResponse.status, 'Не удалось загрузить дорожную карту')
  }
  const statsPayload = await statsResponse.json()

  const allCategories = Array.isArray(comun?.categories) ? comun.categories : []
  const roadmapCategoryIds = new Set(
    (Array.isArray(comun?.roadmap_category_ids) ? comun.roadmap_category_ids : [])
      .map((value: unknown) => Number(value))
      .filter((value: number) => Number.isFinite(value) && value > 0)
  )
  const categories = allCategories.filter((category: any) =>
    roadmapCategoryIds.has(Number(category?.id ?? 0))
  )
  const previewResults = await Promise.all(
    categories.map(async (category: any) => {
      const categorySlug = String(category?.slug ?? '').trim()
      if (!categorySlug) {
        return null
      }
      try {
        const previewUrl = new URL(
          buildComunPostsUrl(slug, { categorySlug }),
          url.origin
        )
        previewUrl.searchParams.set('limit', String(PREVIEW_LIMIT))
        previewUrl.searchParams.set('offset', '0')
        const response = await fetch(previewUrl.toString())
        const payload = await response.json().catch(() => ({}))
        if (!response.ok) {
          return {
            category_slug: categorySlug,
            posts: [],
            total_count: null,
            error: String(payload?.error || 'Не удалось загрузить превью'),
          }
        }
        return {
          category_slug: categorySlug,
          posts: payload?.posts ?? [],
          total_count:
            typeof payload?.total_count === 'number' ? Number(payload.total_count) : null,
          error: null,
        }
      } catch (err) {
        return {
          category_slug: categorySlug,
          posts: [],
          total_count: null,
          error: err instanceof Error ? err.message : 'Ошибка загрузки',
        }
      }
    })
  )
  const selectedCategoryIdSet = new Set(categories.map((category: any) => Number(category?.id ?? 0)))
  const selectedTotalCount = (Array.isArray(statsPayload?.category_counts)
    ? statsPayload.category_counts
    : []
  ).reduce((sum: number, row: any) => {
    const categoryId = Number(row?.category_id ?? 0)
    if (!selectedCategoryIdSet.has(categoryId)) return sum
    return sum + Math.max(Number(row?.count ?? 0) || 0, 0)
  }, 0)

  return {
    comun,
    categoryCounts: statsPayload?.category_counts ?? [],
    totalCount: selectedTotalCount,
    roadmapCategoryIds: Array.from(roadmapCategoryIds),
    categoryPreviews: previewResults.filter(Boolean),
    previewLimit: PREVIEW_LIMIT,
  }
}
