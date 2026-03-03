export type PostTemplateType = 'movie_review'

export type MovieReviewContentKind = 'movie' | 'series'

export type MovieReviewTemplateData = {
  imdb_url?: string
  poster_url?: string
  genre?: string
  content_kind?: MovieReviewContentKind
  title?: string
  original_title?: string
  release_date?: string
  watch_where?: string
}

export type MovieReviewTemplate = {
  type: 'movie_review'
  version: 1
  data: MovieReviewTemplateData
}

export type SitePostTemplate = MovieReviewTemplate

export type PostTemplateTypeOption = {
  value: '' | PostTemplateType
  label: string
}

export const POST_TEMPLATE_TYPE_OPTIONS: PostTemplateTypeOption[] = [
  { value: '', label: 'Обычный пост (без шаблона)' },
  { value: 'movie_review', label: 'Кинообзор' },
]

export const MOVIE_REVIEW_KIND_OPTIONS: Array<{ value: MovieReviewContentKind; label: string }> = [
  { value: 'movie', label: 'Фильм' },
  { value: 'series', label: 'Сериал' },
]

export const createEmptyMovieReviewTemplateData = (): MovieReviewTemplateData => ({
  imdb_url: '',
  poster_url: '',
  genre: '',
  content_kind: 'movie',
  title: '',
  original_title: '',
  release_date: '',
  watch_where: '',
})

const trimOrEmpty = (value: unknown): string => (typeof value === 'string' ? value.trim() : '')

export const normalizeMovieReviewTemplateData = (
  value: Partial<MovieReviewTemplateData> | null | undefined
): MovieReviewTemplateData => {
  const kindRaw = trimOrEmpty(value?.content_kind).toLowerCase()
  const content_kind: MovieReviewContentKind = kindRaw === 'series' ? 'series' : 'movie'
  return {
    imdb_url: trimOrEmpty(value?.imdb_url),
    poster_url: trimOrEmpty(value?.poster_url),
    genre: trimOrEmpty(value?.genre),
    content_kind,
    title: trimOrEmpty(value?.title),
    original_title: trimOrEmpty(value?.original_title),
    release_date: trimOrEmpty(value?.release_date),
    watch_where: trimOrEmpty(value?.watch_where),
  }
}

export const buildPostTemplatePayload = (
  templateType: '' | PostTemplateType,
  movieReviewData: Partial<MovieReviewTemplateData> | null | undefined
): SitePostTemplate | null => {
  if (templateType !== 'movie_review') {
    return null
  }

  const normalized = normalizeMovieReviewTemplateData(movieReviewData)
  const hasMeaningfulField = Boolean(
    normalized.imdb_url ||
      normalized.poster_url ||
      normalized.genre ||
      normalized.content_kind ||
      normalized.title ||
      normalized.original_title ||
      normalized.release_date ||
      normalized.watch_where
  )

  if (!hasMeaningfulField) {
    return null
  }

  return {
    type: 'movie_review',
    version: 1,
    data: normalized,
  }
}

export const isMovieReviewTemplate = (
  template: SitePostTemplate | null | undefined
): template is MovieReviewTemplate => {
  return template?.type === 'movie_review' && typeof template.data === 'object'
}

export const movieReviewKindLabel = (kind: string | null | undefined): string => {
  if (kind === 'series') return 'Сериал'
  return 'Фильм'
}

export const formatMovieReviewReleaseDate = (value: string | null | undefined): string => {
  if (!value) return ''
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return value
  return new Date(timestamp).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}
