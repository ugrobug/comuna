import { error } from '@sveltejs/kit'
import {
  buildTopAuthorsUrl,
  type BackendTopAuthor,
  type BackendTopAuthorPeriod,
} from '$lib/api/backend'

const VALID_PERIODS = new Set<BackendTopAuthorPeriod>(['week', 'month', 'all'])

const normalizePeriod = (value: string | null): BackendTopAuthorPeriod =>
  VALID_PERIODS.has((value ?? '') as BackendTopAuthorPeriod)
    ? (value as BackendTopAuthorPeriod)
    : 'month'

export async function load({ fetch, url }) {
  const period = normalizePeriod(url.searchParams.get('period'))
  const requestUrl = new URL(buildTopAuthorsUrl({ period, limit: 'all' }), url.origin)

  const response = await fetch(requestUrl.toString())
  if (!response.ok) {
    throw error(response.status, 'Не удалось загрузить рейтинг авторов')
  }

  const payload = await response.json()

  return {
    period,
    authors: (payload?.authors ?? []) as BackendTopAuthor[],
    totalAuthors: Number(payload?.total_authors ?? 0) || 0,
  }
}
