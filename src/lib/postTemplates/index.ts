export type PostTemplateType = 'movie_review' | 'post_vote_poll'
export type PostTemplateCode = 'basic' | PostTemplateType

export type TemplateEditorBlockType =
  | 'header'
  | 'list'
  | 'image'
  | 'quote'
  | 'code'
  | 'gallery'
  | 'map'
  | 'compare'
  | 'link'
  | 'embed'
  | 'movie_time'
  | 'movie_card'

export type TemplateEditorBlockOption = {
  type: TemplateEditorBlockType
  label: string
}

export type TemplateEditorBlockSettings = Partial<Record<PostTemplateCode, TemplateEditorBlockType[]>>

export type MovieReviewContentKind = 'movie' | 'series'

export type MovieReviewTemplateData = {
  imdb_url?: string
  poster_url?: string
  genre?: string
  content_kind?: MovieReviewContentKind
  title?: string
  original_title?: string
  release_date?: string
  watch_where?: string[]
}

export type MovieReviewTemplate = {
  type: 'movie_review'
  version: 1
  data: MovieReviewTemplateData
}

export type PostVotePollTemplateItem = {
  post_id: number
  title?: string
  path?: string
  author_username?: string
}

export type PostVotePollTemplateData = {
  question?: string
  items?: PostVotePollTemplateItem[]
  ends_at?: string
  allows_multiple_answers?: boolean
}

export type PostVotePollTemplate = {
  type: 'post_vote_poll'
  version: 1
  data: PostVotePollTemplateData
}

export type SitePostTemplate = MovieReviewTemplate | PostVotePollTemplate

export type PostTemplateTypeOption = {
  value: '' | PostTemplateType
  label: string
}

export const POST_TEMPLATE_TYPE_OPTIONS: PostTemplateTypeOption[] = [
  { value: '', label: 'Пост' },
  { value: 'movie_review', label: 'Кинообзор' },
  { value: 'post_vote_poll', label: 'Голосование за посты' },
]

const POST_TEMPLATE_CODE_VALUES = new Set<PostTemplateCode>([
  'basic',
  'movie_review',
  'post_vote_poll',
])

const TEMPLATE_EDITOR_BLOCK_TYPE_VALUES = new Set<TemplateEditorBlockType>([
  'header',
  'list',
  'image',
  'quote',
  'code',
  'gallery',
  'map',
  'compare',
  'link',
  'embed',
  'movie_time',
  'movie_card',
])

const ALL_TEMPLATE_EDITOR_BLOCK_OPTIONS: TemplateEditorBlockOption[] = [
  { type: 'header', label: 'Заголовок' },
  { type: 'list', label: 'Список' },
  { type: 'image', label: 'Изображение' },
  { type: 'quote', label: 'Цитата' },
  { type: 'code', label: 'Код' },
  { type: 'gallery', label: 'Галерея' },
  { type: 'map', label: 'Карта' },
  { type: 'compare', label: 'Сравнение изображений' },
  { type: 'link', label: 'Ссылка' },
  { type: 'embed', label: 'Встраивание (Embed)' },
  { type: 'movie_time', label: 'Время в фильме' },
  { type: 'movie_card', label: 'Карточка фильма' },
]

const BLOCKS_WITHOUT_MOVIE_CARD = ALL_TEMPLATE_EDITOR_BLOCK_OPTIONS.filter(
  (option) => option.type !== 'movie_card'
)

const TEMPLATE_EDITOR_BLOCKS_BY_TEMPLATE: Record<PostTemplateCode, TemplateEditorBlockOption[]> = {
  basic: BLOCKS_WITHOUT_MOVIE_CARD,
  movie_review: ALL_TEMPLATE_EDITOR_BLOCK_OPTIONS,
  post_vote_poll: BLOCKS_WITHOUT_MOVIE_CARD,
}

export const normalizeAllowedPostTemplateTypes = (value: unknown): PostTemplateCode[] => {
  const source = Array.isArray(value) ? value : typeof value === 'string' ? [value] : []
  const seen = new Set<PostTemplateCode>()
  const normalized: PostTemplateCode[] = []
  for (const item of source) {
    const code = typeof item === 'string' ? item.trim().toLowerCase() : ''
    if (!POST_TEMPLATE_CODE_VALUES.has(code as PostTemplateCode)) continue
    const typedCode = code as PostTemplateCode
    if (seen.has(typedCode)) continue
    seen.add(typedCode)
    normalized.push(typedCode)
  }
  return normalized.length ? normalized : ['basic']
}

export const resolveTemplateCode = (
  templateType: '' | PostTemplateType | null | undefined
): PostTemplateCode => {
  if (templateType === 'movie_review') return 'movie_review'
  if (templateType === 'post_vote_poll') return 'post_vote_poll'
  return 'basic'
}

export const getTemplateEditorBlocks = (
  templateType: '' | PostTemplateType | null | undefined
): TemplateEditorBlockOption[] => {
  return TEMPLATE_EDITOR_BLOCKS_BY_TEMPLATE[resolveTemplateCode(templateType)] ?? []
}

export const getTemplateEditorBlockTypes = (
  templateType: '' | PostTemplateType | null | undefined
): TemplateEditorBlockType[] => {
  return getTemplateEditorBlocks(templateType).map((option) => option.type)
}

export const normalizeTemplateEditorBlockTypes = (value: unknown): TemplateEditorBlockType[] => {
  const source = Array.isArray(value) ? value : typeof value === 'string' ? [value] : []
  const seen = new Set<TemplateEditorBlockType>()
  const normalized: TemplateEditorBlockType[] = []
  for (const item of source) {
    const blockType = typeof item === 'string' ? item.trim().toLowerCase() : ''
    if (!TEMPLATE_EDITOR_BLOCK_TYPE_VALUES.has(blockType as TemplateEditorBlockType)) continue
    const typedBlockType = blockType as TemplateEditorBlockType
    if (seen.has(typedBlockType)) continue
    seen.add(typedBlockType)
    normalized.push(typedBlockType)
  }
  return normalized
}

export const normalizeTemplateEditorBlockSettings = (
  value: unknown
): TemplateEditorBlockSettings => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  const raw = value as Record<string, unknown>
  const normalized: TemplateEditorBlockSettings = {}
  for (const templateCode of POST_TEMPLATE_CODE_VALUES) {
    if (!(templateCode in raw)) continue
    normalized[templateCode] = normalizeTemplateEditorBlockTypes(raw[templateCode])
  }
  return normalized
}

export const resolveEnabledTemplateEditorBlockTypes = (
  templateType: '' | PostTemplateType | null | undefined,
  settings?: TemplateEditorBlockSettings
): TemplateEditorBlockType[] => {
  const templateCode = resolveTemplateCode(templateType)
  const templateDefault = getTemplateEditorBlockTypes(templateType)
  if (!settings || !Object.prototype.hasOwnProperty.call(settings, templateCode)) {
    return templateDefault
  }
  const configured = normalizeTemplateEditorBlockTypes(settings[templateCode])
  const configuredSet = new Set<TemplateEditorBlockType>(configured)
  return templateDefault.filter((blockType) => configuredSet.has(blockType))
}

export const isTemplateEditorBlockEnabled = (
  templateType: '' | PostTemplateType | null | undefined,
  blockType: TemplateEditorBlockType
): boolean => {
  return getTemplateEditorBlockTypes(templateType).includes(blockType)
}

export const MOVIE_REVIEW_KIND_OPTIONS: Array<{ value: MovieReviewContentKind; label: string }> = [
  { value: 'movie', label: 'Фильм' },
  { value: 'series', label: 'Сериал' },
]

export const MOVIE_REVIEW_GENRE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'action', label: 'Боевик' },
  { value: 'adventure', label: 'Приключения' },
  { value: 'animation', label: 'Анимация' },
  { value: 'biography', label: 'Биография' },
  { value: 'comedy', label: 'Комедия' },
  { value: 'crime', label: 'Криминал' },
  { value: 'documentary', label: 'Документальный' },
  { value: 'drama', label: 'Драма' },
  { value: 'family', label: 'Семейный' },
  { value: 'fantasy', label: 'Фэнтези' },
  { value: 'history', label: 'История' },
  { value: 'horror', label: 'Ужасы' },
  { value: 'music', label: 'Музыкальный' },
  { value: 'mystery', label: 'Детектив' },
  { value: 'romance', label: 'Мелодрама' },
  { value: 'sci_fi', label: 'Фантастика' },
  { value: 'sport', label: 'Спорт' },
  { value: 'thriller', label: 'Триллер' },
  { value: 'war', label: 'Военный' },
  { value: 'western', label: 'Вестерн' },
]

export const MOVIE_REVIEW_WATCH_PROVIDER_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'kinopoisk', label: 'Кинопоиск' },
  { value: 'okko', label: 'Okko' },
  { value: 'ivi', label: 'Иви' },
  { value: 'wink', label: 'Wink' },
  { value: 'start', label: 'START' },
  { value: 'premier', label: 'Premier' },
  { value: 'more_tv', label: 'more.tv' },
  { value: 'kion', label: 'KION' },
  { value: 'amediateka', label: 'Амедиатека' },
  { value: 'netflix', label: 'Netflix' },
  { value: 'amazon_prime_video', label: 'Amazon Prime Video' },
  { value: 'disney_plus', label: 'Disney+' },
  { value: 'max', label: 'Max (HBO)' },
  { value: 'apple_tv_plus', label: 'Apple TV+' },
  { value: 'hulu', label: 'Hulu' },
  { value: 'paramount_plus', label: 'Paramount+' },
  { value: 'peacock', label: 'Peacock' },
]

const genreLabelByValue = new Map(
  MOVIE_REVIEW_GENRE_OPTIONS.map((option) => [option.value, option.label])
)

const watchProviderLabelByValue = new Map(
  MOVIE_REVIEW_WATCH_PROVIDER_OPTIONS.map((option) => [option.value, option.label])
)

const movieReviewGenreAliases: Record<string, string> = {
  action: 'action',
  боевик: 'action',
  adventure: 'adventure',
  приключения: 'adventure',
  animation: 'animation',
  анимация: 'animation',
  мультфильм: 'animation',
  biography: 'biography',
  биография: 'biography',
  comedy: 'comedy',
  комедия: 'comedy',
  crime: 'crime',
  криминал: 'crime',
  documentary: 'documentary',
  документальный: 'documentary',
  drama: 'drama',
  драма: 'drama',
  family: 'family',
  семейный: 'family',
  fantasy: 'fantasy',
  фэнтези: 'fantasy',
  history: 'history',
  история: 'history',
  horror: 'horror',
  ужасы: 'horror',
  music: 'music',
  музыкальный: 'music',
  mystery: 'mystery',
  детектив: 'mystery',
  romance: 'romance',
  мелодрама: 'romance',
  sci_fi: 'sci_fi',
  'sci-fi': 'sci_fi',
  sciencefiction: 'sci_fi',
  фантастика: 'sci_fi',
  sport: 'sport',
  спорт: 'sport',
  thriller: 'thriller',
  триллер: 'thriller',
  war: 'war',
  военный: 'war',
  western: 'western',
  вестерн: 'western',
}

const movieReviewWatchProviderAliases: Record<string, string> = {
  kinopoisk: 'kinopoisk',
  'kinopoisk hd': 'kinopoisk',
  kinopoiskhd: 'kinopoisk',
  кинопоиск: 'kinopoisk',
  'кинопоиск hd': 'kinopoisk',
  okko: 'okko',
  ivi: 'ivi',
  иви: 'ivi',
  wink: 'wink',
  start: 'start',
  premier: 'premier',
  more_tv: 'more_tv',
  'more tv': 'more_tv',
  moretv: 'more_tv',
  'more.tv': 'more_tv',
  kion: 'kion',
  amediateka: 'amediateka',
  амедиатека: 'amediateka',
  netflix: 'netflix',
  amazon_prime_video: 'amazon_prime_video',
  amazonprimevideo: 'amazon_prime_video',
  'amazon prime video': 'amazon_prime_video',
  'amazon prime': 'amazon_prime_video',
  'prime video': 'amazon_prime_video',
  disney_plus: 'disney_plus',
  'disney plus': 'disney_plus',
  disneyplus: 'disney_plus',
  'disney+': 'disney_plus',
  max: 'max',
  hbomax: 'max',
  'hbo max': 'max',
  'max (hbo)': 'max',
  apple_tv_plus: 'apple_tv_plus',
  'apple tv': 'apple_tv_plus',
  appletvplus: 'apple_tv_plus',
  'apple tv+': 'apple_tv_plus',
  'apple tv plus': 'apple_tv_plus',
  hulu: 'hulu',
  paramount_plus: 'paramount_plus',
  'paramount plus': 'paramount_plus',
  paramountplus: 'paramount_plus',
  'paramount+': 'paramount_plus',
  peacock: 'peacock',
  'peacock tv': 'peacock',
  peacocktv: 'peacock',
}

const trimOrEmpty = (value: unknown): string => (typeof value === 'string' ? value.trim() : '')

export const createEmptyMovieReviewTemplateData = (): MovieReviewTemplateData => ({
  imdb_url: '',
  poster_url: '',
  genre: '',
  content_kind: 'movie',
  title: '',
  original_title: '',
  release_date: '',
  watch_where: [],
})

export const createEmptyPostVotePollTemplateData = (): PostVotePollTemplateData => ({
  question: '',
  items: [],
  ends_at: '',
  allows_multiple_answers: false,
})

const normalizeMovieReviewGenre = (value: unknown): string => {
  const raw = trimOrEmpty(value)
  if (!raw) return ''
  return movieReviewGenreAliases[raw.toLowerCase()] ?? raw
}

const normalizeMovieReviewWatchWhere = (value: unknown): string[] => {
  const rawItems = Array.isArray(value)
    ? value
    : trimOrEmpty(value)
      ? trimOrEmpty(value)
          .split(/[;,]/)
          .map((item) => item.trim())
      : []

  const normalizedItems: string[] = []
  const seen = new Set<string>()
  for (const rawItem of rawItems) {
    const item = trimOrEmpty(rawItem)
    if (!item) continue
    const normalized = movieReviewWatchProviderAliases[item.toLowerCase()] ?? item
    const dedupeKey = normalized.toLowerCase()
    if (seen.has(dedupeKey)) continue
    seen.add(dedupeKey)
    normalizedItems.push(normalized)
  }
  return normalizedItems
}

export const normalizeMovieReviewTemplateData = (
  value: Partial<MovieReviewTemplateData> | null | undefined
): MovieReviewTemplateData => {
  const kindRaw = trimOrEmpty(value?.content_kind).toLowerCase()
  const content_kind: MovieReviewContentKind = kindRaw === 'series' ? 'series' : 'movie'
  return {
    imdb_url: trimOrEmpty(value?.imdb_url),
    poster_url: trimOrEmpty(value?.poster_url),
    genre: normalizeMovieReviewGenre(value?.genre),
    content_kind,
    title: trimOrEmpty(value?.title),
    original_title: trimOrEmpty(value?.original_title),
    release_date: trimOrEmpty(value?.release_date),
    watch_where: normalizeMovieReviewWatchWhere(value?.watch_where),
  }
}

const normalizePostVotePollItems = (value: unknown): PostVotePollTemplateItem[] => {
  const source = Array.isArray(value) ? value : []
  const seen = new Set<number>()
  const normalized: PostVotePollTemplateItem[] = []
  for (const item of source) {
    if (!item || typeof item !== 'object') continue
    const rawPostId = Number((item as any).post_id ?? (item as any).id)
    const postId = Number.isFinite(rawPostId) ? Math.floor(rawPostId) : 0
    if (postId <= 0 || seen.has(postId)) continue
    seen.add(postId)

    const title = trimOrEmpty((item as any).title)
    const pathRaw = trimOrEmpty((item as any).path)
    const path = pathRaw.startsWith('/') ? pathRaw : ''
    const authorUsername = trimOrEmpty((item as any).author_username)

    const normalizedItem: PostVotePollTemplateItem = { post_id: postId }
    if (title) normalizedItem.title = title
    if (path) normalizedItem.path = path
    if (authorUsername) normalizedItem.author_username = authorUsername

    normalized.push(normalizedItem)
    if (normalized.length >= 10) break
  }
  return normalized
}

const normalizePostVotePollEndsAt = (value: unknown): string => {
  const raw = trimOrEmpty(value)
  if (!raw) return ''
  const timestamp = Date.parse(raw)
  if (!Number.isFinite(timestamp)) return raw
  return new Date(timestamp).toISOString()
}

const normalizePostVotePollAllowsMultipleAnswers = (value: unknown): boolean => {
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value !== 0
  const raw = trimOrEmpty(value).toLowerCase()
  return raw === '1' || raw === 'true' || raw === 'yes' || raw === 'on'
}

export const normalizePostVotePollTemplateData = (
  value: Partial<PostVotePollTemplateData> | null | undefined
): PostVotePollTemplateData => {
  return {
    question: trimOrEmpty(value?.question),
    items: normalizePostVotePollItems(value?.items),
    ends_at: normalizePostVotePollEndsAt(value?.ends_at),
    allows_multiple_answers: normalizePostVotePollAllowsMultipleAnswers(
      value?.allows_multiple_answers
    ),
  }
}

export const buildPostTemplatePayload = (
  templateType: '' | PostTemplateType,
  movieReviewData: Partial<MovieReviewTemplateData> | null | undefined,
  postVotePollData?: Partial<PostVotePollTemplateData> | null | undefined
): SitePostTemplate | null => {
  if (templateType === 'movie_review') {
    const normalized = normalizeMovieReviewTemplateData(movieReviewData)
    const hasMeaningfulField = Boolean(
      normalized.imdb_url ||
        normalized.poster_url ||
        normalized.genre ||
        normalized.content_kind === 'series' ||
        normalized.title ||
        normalized.original_title ||
        normalized.release_date ||
        (normalized.watch_where?.length ?? 0)
    )
    if (!hasMeaningfulField) return null
    return {
      type: 'movie_review',
      version: 1,
      data: normalized,
    }
  }

  if (templateType === 'post_vote_poll') {
    return {
      type: 'post_vote_poll',
      version: 1,
      data: normalizePostVotePollTemplateData(postVotePollData),
    }
  }

  return null
}

export const isMovieReviewTemplate = (
  template: SitePostTemplate | null | undefined
): template is MovieReviewTemplate => {
  return template?.type === 'movie_review' && typeof template.data === 'object'
}

export const isPostVotePollTemplate = (
  template: SitePostTemplate | null | undefined
): template is PostVotePollTemplate => {
  return template?.type === 'post_vote_poll' && typeof template.data === 'object'
}

export const movieReviewKindLabel = (kind: string | null | undefined): string => {
  if (kind === 'series') return 'Сериал'
  return 'Фильм'
}

export const movieReviewGenreLabel = (genre: string | null | undefined): string => {
  if (!genre) return ''
  const normalized = normalizeMovieReviewGenre(genre)
  return genreLabelByValue.get(normalized) ?? genre
}

export const movieReviewWatchProviderLabel = (provider: string | null | undefined): string => {
  if (!provider) return ''
  const normalized = movieReviewWatchProviderAliases[provider.toLowerCase()] ?? provider
  return watchProviderLabelByValue.get(normalized) ?? provider
}

export const movieReviewWatchWhereLabels = (providers: unknown): string[] => {
  const normalized = normalizeMovieReviewWatchWhere(providers)
  return normalized.map((provider) => movieReviewWatchProviderLabel(provider))
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

export const postVotePollOptionLabel = (item: PostVotePollTemplateItem): string => {
  const title = trimOrEmpty(item?.title)
  const looksSerialized =
    title.length >= 48 && !/\s/.test(title) && /^[A-Za-z0-9_+/=-]+$/.test(title)
  if (looksSerialized) {
    return `Пост #${item.post_id}`
  }
  if (title) return title
  return `Пост #${item.post_id}`
}

export const formatPostVotePollDeadline = (value: string | null | undefined): string => {
  if (!value) return ''
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return value
  return new Date(timestamp).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
