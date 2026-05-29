import { deserializeEditorModel } from '$lib/util'

export type BuiltinPostTemplateType =
  | 'movie_review'
  | 'post_vote_poll'
  | 'music_release'
  | 'bug_report'
  | 'tweet'
export type PostTemplateType = BuiltinPostTemplateType | string
export type PostTemplateCode = 'basic' | PostTemplateType

export type TemplateEditorBlockType =
  | 'toc'
  | 'header'
  | 'list'
  | 'table'
  | 'image'
  | 'quote'
  | 'callout'
  | 'author'
  | 'code'
  | 'poll'
  | 'divider'
  | 'spoiler'
  | 'gallery'
  | 'map'
  | 'compare'
  | 'link'
  | 'embed'
  | 'post_link'
  | 'music'
  | 'movie_time'
  | 'movie_card'
  | 'post_rating'

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
  author_rating?: string
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

export type MusicReleaseTemplateData = {
  cover_image_url?: string
  release_date?: string
  album_url?: string
  artist_name?: string
  release_title?: string
  country?: string
  city?: string
  style?: string
}

export type MusicReleaseTemplate = {
  type: 'music_release'
  version: 1
  data: MusicReleaseTemplateData
}

export type BugReportStatus = 'review' | 'in_progress' | 'resolved' | 'rejected'

export type BugReportTemplateData = {
  status?: BugReportStatus
  platforms?: string[]
  browsers?: string[]
  error_code?: string
  screenshot_url?: string
}

export type BugReportTemplate = {
  type: 'bug_report'
  version: 1
  data: BugReportTemplateData
}

export type TweetTemplate = {
  type: 'tweet'
  version: 1
  data: Record<string, never>
}

export type CustomPostTemplate = {
  type: string
  version: 1
  data: Record<string, never>
}

export type SitePostTemplate =
  | MovieReviewTemplate
  | PostVotePollTemplate
  | MusicReleaseTemplate
  | BugReportTemplate
  | TweetTemplate
  | CustomPostTemplate

export type PostTemplateTypeOption = {
  value: '' | PostTemplateType
  label: string
  description?: string
}

export const POST_TEMPLATE_TYPE_OPTIONS: PostTemplateTypeOption[] = [
  { value: '', label: 'Пост' },
  { value: 'movie_review', label: 'Кинообзор' },
  { value: 'post_vote_poll', label: 'Голосование за посты' },
  { value: 'music_release', label: 'Музыкальный релиз' },
  { value: 'bug_report', label: 'Баг-репорт', description: 'Платформа, браузер, код ошибки и скриншот.' },
  { value: 'tweet', label: 'Твит', description: 'До 280 символов и один медиаблок с изображениями.' },
]

const POST_TEMPLATE_CODE_RE = /^[a-z0-9][a-z0-9_-]{0,159}$/

const TEMPLATE_EDITOR_BLOCK_TYPE_VALUES = new Set<TemplateEditorBlockType>([
  'toc',
  'header',
  'list',
  'table',
  'image',
  'quote',
  'callout',
  'author',
  'code',
  'poll',
  'divider',
  'spoiler',
  'gallery',
  'map',
  'compare',
  'link',
  'embed',
  'post_link',
  'music',
  'movie_time',
  'movie_card',
  'post_rating',
])

const ALL_TEMPLATE_EDITOR_BLOCK_OPTIONS: TemplateEditorBlockOption[] = [
  { type: 'toc', label: 'Оглавление' },
  { type: 'header', label: 'Заголовок' },
  { type: 'list', label: 'Список' },
  { type: 'table', label: 'Таблица' },
  { type: 'image', label: 'Изображение' },
  { type: 'quote', label: 'Цитата' },
  { type: 'callout', label: 'Врезка' },
  { type: 'author', label: 'Автор' },
  { type: 'code', label: 'Код' },
  { type: 'poll', label: 'Опрос' },
  { type: 'divider', label: 'Разделитель' },
  { type: 'spoiler', label: 'Спойлер' },
  { type: 'gallery', label: 'Галерея' },
  { type: 'map', label: 'Карта' },
  { type: 'compare', label: 'Сравнение изображений' },
  { type: 'link', label: 'Ссылка' },
  { type: 'embed', label: 'Встраивание (Embed)' },
  { type: 'post_link', label: 'Ссылка на пост' },
  { type: 'music', label: 'Музыка' },
  { type: 'movie_time', label: 'Время в фильме' },
  { type: 'movie_card', label: 'Карточка фильма' },
  { type: 'post_rating', label: 'Рейтинг' },
]

const BLOCKS_WITHOUT_MOVIE_CARD = ALL_TEMPLATE_EDITOR_BLOCK_OPTIONS.filter(
  (option) => option.type !== 'movie_card'
)

const TEMPLATE_EDITOR_BLOCKS_BY_TEMPLATE: Record<string, TemplateEditorBlockOption[]> = {
  basic: BLOCKS_WITHOUT_MOVIE_CARD,
  movie_review: ALL_TEMPLATE_EDITOR_BLOCK_OPTIONS,
  post_vote_poll: BLOCKS_WITHOUT_MOVIE_CARD,
  music_release: BLOCKS_WITHOUT_MOVIE_CARD,
  bug_report: BLOCKS_WITHOUT_MOVIE_CARD,
  tweet: ALL_TEMPLATE_EDITOR_BLOCK_OPTIONS.filter((option) => option.type === 'gallery'),
}

export const TWEET_TEMPLATE_MAX_LENGTH = 280
export const BUG_REPORT_STATUS_OPTIONS: Array<{ value: BugReportStatus; label: string }> = [
  { value: 'review', label: 'Рассмотрение' },
  { value: 'in_progress', label: 'В работе' },
  { value: 'resolved', label: 'Решена' },
  { value: 'rejected', label: 'Отклонена' },
]
export const BUG_REPORT_PLATFORM_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'web', label: 'Web' },
  { value: 'windows', label: 'Windows' },
  { value: 'macos', label: 'macOS' },
  { value: 'linux', label: 'Linux' },
  { value: 'android', label: 'Android' },
  { value: 'ios', label: 'iOS' },
]
export const BUG_REPORT_BROWSER_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'chrome', label: 'Chrome' },
  { value: 'safari', label: 'Safari' },
  { value: 'firefox', label: 'Firefox' },
  { value: 'edge', label: 'Edge' },
  { value: 'opera', label: 'Opera' },
  { value: 'yandex_browser', label: 'Яндекс Браузер' },
  { value: 'samsung_internet', label: 'Samsung Internet' },
  { value: 'arc', label: 'Arc' },
  { value: 'other', label: 'Другое' },
]

const normalizeTemplateCode = (value: unknown): PostTemplateCode | '' => {
  const code = typeof value === 'string' ? value.trim().toLowerCase() : ''
  if (!code || !POST_TEMPLATE_CODE_RE.test(code)) return ''
  return code as PostTemplateCode
}

const templateOptionKey = (value: string) => (value ? value : 'basic')

export const normalizePostTemplateTypeOptions = (value: unknown): PostTemplateTypeOption[] => {
  const source = Array.isArray(value) ? value : []
  const normalized: PostTemplateTypeOption[] = []
  const seen = new Set<string>()
  for (const item of source) {
    const rawValue = (item as any)?.value
    const rawCode = rawValue === '' ? 'basic' : normalizeTemplateCode(rawValue)
    const label = typeof (item as any)?.label === 'string' ? (item as any).label.trim() : ''
    const description =
      typeof (item as any)?.description === 'string' ? (item as any).description.trim() : ''
    if (!rawCode || !label) continue
    const optionValue = rawCode === 'basic' ? '' : rawCode
    const key = templateOptionKey(optionValue)
    if (seen.has(key)) continue
    seen.add(key)
    normalized.push({ value: optionValue, label, ...(description ? { description } : {}) })
  }
  return normalized.length ? normalized : POST_TEMPLATE_TYPE_OPTIONS
}

export const normalizeAllowedPostTemplateTypes = (value: unknown): PostTemplateCode[] => {
  const source = Array.isArray(value) ? value : typeof value === 'string' ? [value] : []
  const seen = new Set<PostTemplateCode>()
  const normalized: PostTemplateCode[] = []
  for (const item of source) {
    const typedCode = normalizeTemplateCode(item)
    if (!typedCode) continue
    if (seen.has(typedCode)) continue
    seen.add(typedCode)
    normalized.push(typedCode)
  }
  return normalized.length ? normalized : ['basic']
}

export const normalizeAllowedPostTemplateTypeOverrides = (value: unknown): PostTemplateCode[] => {
  const source = Array.isArray(value) ? value : typeof value === 'string' ? [value] : []
  const seen = new Set<PostTemplateCode>()
  const normalized: PostTemplateCode[] = []
  for (const item of source) {
    const typedCode = normalizeTemplateCode(item)
    if (!typedCode) continue
    if (seen.has(typedCode)) continue
    seen.add(typedCode)
    normalized.push(typedCode)
  }
  return normalized
}

export const isRecognizedPostTemplateType = (value: unknown): value is PostTemplateType => {
  const code = normalizeTemplateCode(value)
  return Boolean(code && code !== 'basic')
}

export const isTweetTemplateType = (
  value: '' | PostTemplateType | null | undefined
): value is 'tweet' => normalizeTemplateCode(value) === 'tweet'

export const resolveTemplateCode = (
  templateType: '' | PostTemplateType | null | undefined
): PostTemplateCode => {
  const code = normalizeTemplateCode(templateType)
  if (code) return code
  return 'basic'
}

export const getTemplateEditorBlocks = (
  templateType: '' | PostTemplateType | null | undefined
): TemplateEditorBlockOption[] => {
  return (
    TEMPLATE_EDITOR_BLOCKS_BY_TEMPLATE[resolveTemplateCode(templateType)] ??
    ALL_TEMPLATE_EDITOR_BLOCK_OPTIONS
  )
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
  for (const [rawTemplateCode, rawBlocks] of Object.entries(raw)) {
    const templateCode = normalizeTemplateCode(rawTemplateCode)
    if (!templateCode) continue
    normalized[templateCode] = normalizeTemplateEditorBlockTypes(rawBlocks)
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

export const MUSIC_RELEASE_STYLE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'pop', label: 'Поп' },
  { value: 'rock', label: 'Рок' },
  { value: 'indie', label: 'Инди' },
  { value: 'alternative', label: 'Альтернатива' },
  { value: 'metal', label: 'Метал' },
  { value: 'punk', label: 'Панк' },
  { value: 'hip_hop', label: 'Хип-хоп' },
  { value: 'rap', label: 'Рэп' },
  { value: 'rnb', label: 'R&B' },
  { value: 'electronic', label: 'Электроника' },
  { value: 'edm', label: 'EDM' },
  { value: 'house', label: 'House' },
  { value: 'techno', label: 'Techno' },
  { value: 'trance', label: 'Trance' },
  { value: 'drum_and_bass', label: 'Drum & Bass' },
  { value: 'dubstep', label: 'Dubstep' },
  { value: 'ambient', label: 'Ambient' },
  { value: 'lo_fi', label: 'Lo-fi' },
  { value: 'jazz', label: 'Джаз' },
  { value: 'blues', label: 'Блюз' },
  { value: 'soul', label: 'Соул' },
  { value: 'funk', label: 'Фанк' },
  { value: 'reggae', label: 'Регги' },
  { value: 'ska', label: 'Ска' },
  { value: 'folk', label: 'Фолк' },
  { value: 'country', label: 'Кантри' },
  { value: 'classical', label: 'Классика' },
  { value: 'soundtrack', label: 'Саундтрек' },
]

const genreLabelByValue = new Map(
  MOVIE_REVIEW_GENRE_OPTIONS.map((option) => [option.value, option.label])
)

const watchProviderLabelByValue = new Map(
  MOVIE_REVIEW_WATCH_PROVIDER_OPTIONS.map((option) => [option.value, option.label])
)

const musicReleaseStyleLabelByValue = new Map(
  MUSIC_RELEASE_STYLE_OPTIONS.map((option) => [option.value, option.label])
)

const bugReportStatusLabelByValue = new Map(
  BUG_REPORT_STATUS_OPTIONS.map((option) => [option.value, option.label])
)

const bugReportPlatformLabelByValue = new Map(
  BUG_REPORT_PLATFORM_OPTIONS.map((option) => [option.value, option.label])
)

const bugReportBrowserLabelByValue = new Map(
  BUG_REPORT_BROWSER_OPTIONS.map((option) => [option.value, option.label])
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

const musicReleaseStyleAliases: Record<string, string> = {
  pop: 'pop',
  поп: 'pop',
  rock: 'rock',
  рок: 'rock',
  indie: 'indie',
  инди: 'indie',
  alternative: 'alternative',
  альтернативный: 'alternative',
  альтернатива: 'alternative',
  metal: 'metal',
  метал: 'metal',
  металл: 'metal',
  punk: 'punk',
  панк: 'punk',
  hip_hop: 'hip_hop',
  'hip-hop': 'hip_hop',
  хипхоп: 'hip_hop',
  'хип-хоп': 'hip_hop',
  rap: 'rap',
  рэп: 'rap',
  rnb: 'rnb',
  'r&b': 'rnb',
  electronic: 'electronic',
  электроника: 'electronic',
  edm: 'edm',
  house: 'house',
  techno: 'techno',
  trance: 'trance',
  drum_and_bass: 'drum_and_bass',
  'drum and bass': 'drum_and_bass',
  dnb: 'drum_and_bass',
  dubstep: 'dubstep',
  ambient: 'ambient',
  эмбиент: 'ambient',
  lo_fi: 'lo_fi',
  lofi: 'lo_fi',
  'lo-fi': 'lo_fi',
  jazz: 'jazz',
  джаз: 'jazz',
  blues: 'blues',
  блюз: 'blues',
  soul: 'soul',
  соул: 'soul',
  funk: 'funk',
  фанк: 'funk',
  reggae: 'reggae',
  регги: 'reggae',
  ska: 'ska',
  ска: 'ska',
  folk: 'folk',
  фолк: 'folk',
  country: 'country',
  кантри: 'country',
  classical: 'classical',
  классика: 'classical',
  soundtrack: 'soundtrack',
  саундтрек: 'soundtrack',
}

const bugReportStatusAliases: Record<string, BugReportStatus> = {
  review: 'review',
  рассмотрение: 'review',
  in_progress: 'in_progress',
  'в работе': 'in_progress',
  resolved: 'resolved',
  решена: 'resolved',
  rejected: 'rejected',
  отклонена: 'rejected',
}

const bugReportPlatformAliases: Record<string, string> = {
  web: 'web',
  веб: 'web',
  браузер: 'web',
  windows: 'windows',
  win: 'windows',
  виндовс: 'windows',
  macos: 'macos',
  'mac os': 'macos',
  mac: 'macos',
  linux: 'linux',
  линукс: 'linux',
  android: 'android',
  андроид: 'android',
  ios: 'ios',
  айос: 'ios',
  iphone: 'ios',
  ipad: 'ios',
}

const bugReportBrowserAliases: Record<string, string> = {
  chrome: 'chrome',
  'google chrome': 'chrome',
  safari: 'safari',
  firefox: 'firefox',
  'mozilla firefox': 'firefox',
  edge: 'edge',
  'microsoft edge': 'edge',
  opera: 'opera',
  yandex_browser: 'yandex_browser',
  'yandex browser': 'yandex_browser',
  'яндекс браузер': 'yandex_browser',
  samsung_internet: 'samsung_internet',
  'samsung internet': 'samsung_internet',
  arc: 'arc',
  other: 'other',
  другое: 'other',
}

const trimOrEmpty = (value: unknown): string => (typeof value === 'string' ? value.trim() : '')

export const createEmptyMovieReviewTemplateData = (): MovieReviewTemplateData => ({
  imdb_url: '',
  poster_url: '',
  genre: '',
  content_kind: 'movie',
  author_rating: '',
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

export const createEmptyMusicReleaseTemplateData = (): MusicReleaseTemplateData => ({
  cover_image_url: '',
  release_date: '',
  album_url: '',
  artist_name: '',
  release_title: '',
  country: '',
  city: '',
  style: '',
})

export const createEmptyBugReportTemplateData = (): BugReportTemplateData => ({
  status: 'review',
  platforms: [],
  browsers: [],
  error_code: '',
  screenshot_url: '',
})

const normalizeMovieReviewGenre = (value: unknown): string => {
  const raw = trimOrEmpty(value)
  if (!raw) return ''
  return movieReviewGenreAliases[raw.toLowerCase()] ?? raw
}

const parseMovieReviewAuthorRatingNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  const raw = trimOrEmpty(value).replace(',', '.')
  if (!raw) return null
  const numeric = Number(raw)
  if (!Number.isFinite(numeric)) return null
  return numeric
}

const normalizeMovieReviewAuthorRating = (value: unknown): string => {
  const parsed = parseMovieReviewAuthorRatingNumber(value)
  if (parsed === null) return ''
  const clamped = Math.max(0, Math.min(10, parsed))
  const rounded = Math.round(clamped * 10) / 10
  if (Number.isInteger(rounded)) return String(rounded)
  return rounded.toFixed(1).replace(/\.0$/, '')
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

const normalizeMusicReleaseStyle = (value: unknown): string => {
  const raw = trimOrEmpty(value)
  if (!raw) return ''
  return musicReleaseStyleAliases[raw.toLowerCase()] ?? raw
}

const normalizeBugReportStatus = (value: unknown): BugReportStatus => {
  const raw = trimOrEmpty(value).toLowerCase()
  return bugReportStatusAliases[raw] ?? 'review'
}

const normalizeBugReportMultiValue = (
  value: unknown,
  aliases: Record<string, string>,
  allowedValues: Set<string>
): string[] => {
  const source = Array.isArray(value)
    ? value
    : trimOrEmpty(value)
      ? trimOrEmpty(value)
          .split(/[;,]/)
          .map((item) => item.trim())
      : []

  const normalized: string[] = []
  const seen = new Set<string>()
  for (const rawItem of source) {
    const item = trimOrEmpty(rawItem)
    if (!item) continue
    const normalizedValue = aliases[item.toLowerCase()] ?? item.toLowerCase()
    if (!allowedValues.has(normalizedValue) || seen.has(normalizedValue)) continue
    seen.add(normalizedValue)
    normalized.push(normalizedValue)
  }
  return normalized
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
    author_rating: normalizeMovieReviewAuthorRating(value?.author_rating),
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

export const normalizeMusicReleaseTemplateData = (
  value: Partial<MusicReleaseTemplateData> | null | undefined
): MusicReleaseTemplateData => {
  return {
    cover_image_url: trimOrEmpty(value?.cover_image_url),
    release_date: trimOrEmpty(value?.release_date),
    album_url: trimOrEmpty(value?.album_url),
    artist_name: trimOrEmpty(value?.artist_name),
    release_title: trimOrEmpty(value?.release_title),
    country: trimOrEmpty(value?.country),
    city: trimOrEmpty(value?.city),
    style: normalizeMusicReleaseStyle(value?.style),
  }
}

export const normalizeBugReportTemplateData = (
  value: Partial<BugReportTemplateData> | null | undefined
): BugReportTemplateData => {
  return {
    status: normalizeBugReportStatus(value?.status),
    platforms: normalizeBugReportMultiValue(
      value?.platforms ?? (value as any)?.platform,
      bugReportPlatformAliases,
      new Set(BUG_REPORT_PLATFORM_OPTIONS.map((option) => option.value))
    ),
    browsers: normalizeBugReportMultiValue(
      value?.browsers ?? (value as any)?.browser,
      bugReportBrowserAliases,
      new Set(BUG_REPORT_BROWSER_OPTIONS.map((option) => option.value))
    ),
    error_code: trimOrEmpty(value?.error_code).slice(0, 4000),
    screenshot_url: trimOrEmpty(value?.screenshot_url),
  }
}

export const buildPostTemplatePayload = (
  templateType: '' | PostTemplateType,
  movieReviewData: Partial<MovieReviewTemplateData> | null | undefined,
  postVotePollData?: Partial<PostVotePollTemplateData> | null | undefined,
  musicReleaseData?: Partial<MusicReleaseTemplateData> | null | undefined,
  bugReportData?: Partial<BugReportTemplateData> | null | undefined
): SitePostTemplate | null => {
  if (templateType === 'movie_review') {
    const normalized = normalizeMovieReviewTemplateData(movieReviewData)
    const hasMeaningfulField = Boolean(
      normalized.imdb_url ||
        normalized.poster_url ||
        normalized.genre ||
        normalized.content_kind === 'series' ||
        normalized.author_rating ||
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

  if (templateType === 'music_release') {
    const normalized = normalizeMusicReleaseTemplateData(musicReleaseData)
    const hasMeaningfulField = Boolean(
      normalized.cover_image_url ||
        normalized.release_date ||
        normalized.album_url ||
        normalized.artist_name ||
        normalized.release_title ||
        normalized.country ||
        normalized.city ||
        normalized.style
    )
    if (!hasMeaningfulField) return null
    return {
      type: 'music_release',
      version: 1,
      data: normalized,
    }
  }

  if (templateType === 'bug_report') {
    return {
      type: 'bug_report',
      version: 1,
      data: normalizeBugReportTemplateData(bugReportData),
    }
  }

  if (templateType === 'tweet') {
    return {
      type: 'tweet',
      version: 1,
      data: {},
    }
  }

  const customTemplateType = normalizeTemplateCode(templateType)
  if (customTemplateType && customTemplateType !== 'basic') {
    return {
      type: customTemplateType,
      version: 1,
      data: {},
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

export const isMusicReleaseTemplate = (
  template: SitePostTemplate | null | undefined
): template is MusicReleaseTemplate => {
  return template?.type === 'music_release' && typeof template.data === 'object'
}

export const isBugReportTemplate = (
  template: SitePostTemplate | null | undefined
): template is BugReportTemplate => {
  return template?.type === 'bug_report' && typeof template.data === 'object'
}

export const isTweetTemplate = (
  template: SitePostTemplate | null | undefined
): template is TweetTemplate => {
  return template?.type === 'tweet' && typeof template.data === 'object'
}

const stripHtmlTags = (value: string): string =>
  value.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()

const tweetTextFromBlock = (block: any): string => {
  const blockType = typeof block?.type === 'string' ? block.type.trim().toLowerCase() : ''
  if (blockType !== 'paragraph') return ''
  return stripHtmlTags(String(block?.data?.text || ''))
}

const tweetEditorBlocks = (content: string): any[] => {
  const raw = typeof content === 'string' ? content.trim() : ''
  if (!raw) return []
  try {
    const parsed = deserializeEditorModel(raw)
    return Array.isArray(parsed?.blocks) ? parsed.blocks : []
  } catch {
    return []
  }
}

export const tweetTemplateCharacterCount = (content: string): number => {
  const blocks = tweetEditorBlocks(content)
  if (!blocks.length) {
    return stripHtmlTags(content || '').length
  }
  const text = blocks
    .map((block) => tweetTextFromBlock(block))
    .filter(Boolean)
    .join('\n')
    .trim()
  return text.length
}

export const tweetTemplateMediaBlockCount = (content: string): number => {
  return tweetEditorBlocks(content).filter((block) => {
    const blockType = typeof block?.type === 'string' ? block.type.trim().toLowerCase() : ''
    return blockType === 'image' || blockType === 'gallery'
  }).length
}

export const validateTweetTemplateContent = (content: string): string => {
  const characters = tweetTemplateCharacterCount(content)
  if (characters > TWEET_TEMPLATE_MAX_LENGTH) {
    return `Твит не может быть длиннее ${TWEET_TEMPLATE_MAX_LENGTH} символов.`
  }
  const mediaBlocks = tweetTemplateMediaBlockCount(content)
  if (mediaBlocks > 1) {
    return 'В шаблоне «Твит» можно использовать только один медиаблок.'
  }
  return ''
}

export const movieReviewKindLabel = (kind: string | null | undefined): string => {
  if (kind === 'series') return 'Сериал'
  return 'Фильм'
}

export const movieReviewAuthorRatingValue = (value: unknown): number | null => {
  const normalized = normalizeMovieReviewAuthorRating(value)
  if (!normalized) return null
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : null
}

export const movieReviewAuthorRatingLabel = (value: unknown): string => {
  const rating = movieReviewAuthorRatingValue(value)
  if (rating === null) return ''
  return `${Number.isInteger(rating) ? String(rating) : rating.toFixed(1)} / 10`
}

export const movieReviewAuthorRatingTone = (
  value: unknown
): 'green' | 'yellow' | 'red' | '' => {
  const rating = movieReviewAuthorRatingValue(value)
  if (rating === null) return ''
  if (rating >= 8) return 'green'
  if (rating >= 5) return 'yellow'
  return 'red'
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

export const musicReleaseStyleLabel = (style: string | null | undefined): string => {
  if (!style) return ''
  const normalized = normalizeMusicReleaseStyle(style)
  return musicReleaseStyleLabelByValue.get(normalized) ?? style
}

export const bugReportStatusLabel = (status: string | null | undefined): string => {
  if (!status) return bugReportStatusLabelByValue.get('review') ?? 'Рассмотрение'
  const normalized = normalizeBugReportStatus(status)
  return bugReportStatusLabelByValue.get(normalized) ?? status
}

export const bugReportStatusTone = (
  status: string | null | undefined
): 'amber' | 'blue' | 'green' | 'red' => {
  const normalized = normalizeBugReportStatus(status)
  if (normalized === 'resolved') return 'green'
  if (normalized === 'rejected') return 'red'
  if (normalized === 'in_progress') return 'blue'
  return 'amber'
}

export const bugReportPlatformLabel = (platform: string | null | undefined): string => {
  if (!platform) return ''
  const normalized = bugReportPlatformAliases[platform.toLowerCase()] ?? platform
  return bugReportPlatformLabelByValue.get(normalized) ?? platform
}

export const bugReportBrowserLabel = (browser: string | null | undefined): string => {
  if (!browser) return ''
  const normalized = bugReportBrowserAliases[browser.toLowerCase()] ?? browser
  return bugReportBrowserLabelByValue.get(normalized) ?? browser
}

export const bugReportPlatformLabels = (platforms: unknown): string[] =>
  normalizeBugReportMultiValue(
    platforms,
    bugReportPlatformAliases,
    new Set(BUG_REPORT_PLATFORM_OPTIONS.map((option) => option.value))
  ).map((platform) => bugReportPlatformLabel(platform))

export const bugReportBrowserLabels = (browsers: unknown): string[] =>
  normalizeBugReportMultiValue(
    browsers,
    bugReportBrowserAliases,
    new Set(BUG_REPORT_BROWSER_OPTIONS.map((option) => option.value))
  ).map((browser) => bugReportBrowserLabel(browser))

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

export const formatMusicReleaseDate = (value: string | null | undefined): string => {
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
