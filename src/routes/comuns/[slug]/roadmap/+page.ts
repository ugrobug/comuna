import { buildComunPostsUrl, buildComunUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

const PREVIEW_LIMIT = 12

export const load = async ({ fetch, params, url }) => {
  const slug = params.slug

  const comunResponse = await fetch(new URL(buildComunUrl(slug), url.origin).toString())
  if (!comunResponse.ok) {
    if (comunResponse.status === 404) {
      throw error(404, 'Комуна не найдена')
    }
    throw error(comunResponse.status, 'Не удалось загрузить коммуну')
  }
  const comunPayload = await comunResponse.json()
  const comun = comunPayload?.comun ?? null

  const statsUrl = new URL(buildComunPostsUrl(slug), url.origin)
  statsUrl.searchParams.set('limit', '1')
  const statsResponse = await fetch(statsUrl.toString())
  if (!statsResponse.ok) {
    if (statsResponse.status === 404) {
      throw error(404, 'Комуна не найдена')
    }
    throw error(statsResponse.status, 'Не удалось загрузить дорожную карту')
  }
  const statsPayload = await statsResponse.json()

  const categories = Array.isArray(comun?.categories) ? comun.categories : []
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

  return {
    comun,
    categoryCounts: statsPayload?.category_counts ?? [],
    totalCount:
      typeof statsPayload?.total_count === 'number' ? Number(statsPayload.total_count) : 0,
    uncategorizedCount:
      typeof statsPayload?.uncategorized_count === 'number'
        ? Number(statsPayload.uncategorized_count)
        : 0,
    categoryPreviews: previewResults.filter(Boolean),
    previewLimit: PREVIEW_LIMIT,
  }
}
