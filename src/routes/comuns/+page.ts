import { browser } from '$app/environment'
import { buildComunsCatalogUrl } from '$lib/api/backend'
import {
  languageFromPathname,
  normalizeInterfaceLanguage,
  originalPostLanguage,
} from '$lib/postLanguages'
import { locale } from '$lib/translations'
import { error } from '@sveltejs/kit'
import { get } from 'svelte/store'

const COMUNS_PAGE_SIZE = 20

export const load = async ({ fetch, parent, url }) => {
  await parent()
  const page = Math.max(Number(url.searchParams.get('page')) || 1, 1)
  const query = (url.searchParams.get('q') || '').trim()
  const scope = url.searchParams.get('scope') === 'mine' ? 'mine' : 'all'
  const language =
    (browser ? normalizeInterfaceLanguage(get(locale)) : null) ??
    languageFromPathname(url.pathname) ??
    originalPostLanguage
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
      language,
    }
  }
  const response = await fetch(
    new URL(
      buildComunsCatalogUrl({ page, limit: COMUNS_PAGE_SIZE, q: query, language }),
      url.origin
    ).toString()
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
    language,
  }
}
