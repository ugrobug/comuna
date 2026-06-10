import { buildComunsCatalogUrl } from '$lib/api/backend'
import { error } from '@sveltejs/kit'

const COMUNS_PAGE_SIZE = 20

export const load = async ({ fetch, url }) => {
  const page = Math.max(Number(url.searchParams.get('page')) || 1, 1)
  const query = (url.searchParams.get('q') || '').trim()
  const scope = url.searchParams.get('scope') === 'mine' ? 'mine' : 'all'
  if (scope === 'mine') {
    return {
      comuns: [],
      page,
      limit: COMUNS_PAGE_SIZE,
      totalComuns: 0,
      totalPages: 0,
      hasNext: false,
      hasPrevious: page > 1,
      query,
      scope,
    }
  }
  const response = await fetch(
    new URL(buildComunsCatalogUrl({ page, limit: COMUNS_PAGE_SIZE, q: query }), url.origin).toString()
  )
  if (!response.ok) {
    throw error(response.status, 'Не удалось загрузить сообщества')
  }
  const data = await response.json()
  return {
    comuns: data?.comuns ?? [],
    page: Number(data?.page ?? page) || page,
    limit: Number(data?.limit ?? COMUNS_PAGE_SIZE) || COMUNS_PAGE_SIZE,
    totalComuns: Number(data?.total_comuns ?? 0) || 0,
    totalPages: Number(data?.total_pages ?? 0) || 0,
    hasNext: Boolean(data?.has_next),
    hasPrevious: Boolean(data?.has_previous),
    query: data?.query ?? query,
    scope,
  }
}
