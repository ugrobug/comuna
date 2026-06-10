import { browser } from '$app/environment'
import {
  buildAuthChatMessagesUrl,
  buildAuthChatReportBlockUrl,
  buildAuthChatsUrl,
  buildAuthChatUrl,
  buildBackendPostPath,
  buildPostDetailUrl,
  buildSearchUrl,
  type BackendSiteChat,
  type BackendSiteChatMessage,
  type BackendSiteChatReport,
  type BackendPostRating,
  getBackendBaseUrl,
} from '$lib/api/backend'
import type {
  MovieReviewTemplateData,
  PostVotePollTemplateItem,
  SitePostTemplate,
} from '$lib/postTemplates'
import { loadBackendFeedSettings, resetBackendFeedSettingsSync } from '$lib/settings'
import { writable, get } from 'svelte/store'

export type SiteAuthorLink = {
  id?: number
  username: string
  title?: string | null
  channel_url?: string | null
  avatar_url?: string | null
  auto_publish?: boolean
  publish_delay_days?: number
  notify_comments?: boolean
  invite_url?: string | null
  author_rating?: number
  linked_comun_slug?: string | null
  linked_comun_name?: string | null
}

export type SiteUser = {
  id: number
  username: string
  display_name?: string | null
  email?: string | null
  email_verified?: boolean
  telegram_linked?: boolean
  telegram_username?: string | null
  vk_linked?: boolean
  vk_username?: string | null
  avatar_url?: string | null
  is_staff?: boolean
  is_author: boolean
  authors: SiteAuthorLink[]
  max_author_rating?: number
  can_create_comun?: boolean
  create_comun_min_author_rating?: number
}

export type SiteUserPost = {
  id: number
  title: string
  content: string
  template?: SitePostTemplate | null
  enabled_template_editor_blocks?: string[]
  post_ratings?: Record<string, BackendPostRating>
  post_rating?: BackendPostRating | null
  created_at: string
  updated_at?: string
  is_pending?: boolean
  is_draft?: boolean
  draft_share_token?: string | null
  publish_at?: string | null
  comun_slug?: string | null
  comun?: {
    id?: number
    name?: string | null
    slug?: string | null
  } | null
  comun_category_id?: number | null
  comun_category?: {
    id?: number
    name?: string | null
    slug?: string | null
  } | null
  tags?: { name: string; lemma?: string | null }[]
  author: {
    username: string
    title?: string | null
    avatar_url?: string | null
  }
}

export type SiteNotificationItem = {
  id: number
  event_key: string
  title: string
  message: string
  link_url?: string | null
  payload?: Record<string, unknown>
  group_key?: string
  group_count?: number
  is_read: boolean
  read_at?: string | null
  created_at: string
  updated_at?: string | null
}

export type SiteNotificationEventSetting = {
  key: string
  title: string
  description?: string
  site_enabled: boolean
  telegram_enabled: boolean
  push_enabled: boolean
  supports_grouping: boolean
  grouping_period: 'none' | 'day' | 'week'
  default_grouping_period: 'none' | 'day' | 'week'
  grouping_options: Array<{ value: 'none' | 'day' | 'week'; label: string }>
  default_site_enabled: boolean
  default_telegram_enabled: boolean
  default_push_enabled: boolean
}

export type SiteNotificationSettingsResponse = {
  events: SiteNotificationEventSetting[]
  telegram: {
    linked: boolean
    username?: string | null
    first_name?: string | null
  }
  push: {
    configured: boolean
    registered_devices_count: number
    active_platforms: string[]
  }
}

export type SiteChatListResponse = {
  chats: BackendSiteChat[]
  total: number
  limit: number
  offset: number
}

export type SiteChatDetailResponse = {
  chat: BackendSiteChat
  messages: BackendSiteChatMessage[]
}

export type SiteStaticPageContent = {
  slug: string
  title: string
  content: string
  exists: boolean
  updated_at?: string | null
  updated_by?: {
    id: number
    username: string
  } | null
}

export type VotePollPostCandidate = PostVotePollTemplateItem

const TOKEN_KEY = 'comuna.site.token'
const COOKIE_AUTH_SENTINEL = '__cookie__'

const initialToken: string | null = null

export const siteToken = writable<string | null>(initialToken)
export const siteUser = writable<SiteUser | null>(null)

const buildUrl = (path: string) => `${getBackendBaseUrl()}${path}`

const normalizeNotificationGroupingPeriod = (value: any): 'none' | 'day' | 'week' => {
  const text = String(value || '').trim()
  return text === 'day' || text === 'week' ? text : 'none'
}

const normalizeSiteNotificationEventSetting = (value: any): SiteNotificationEventSetting => ({
  key: String(value?.key || ''),
  title: String(value?.title || value?.key || ''),
  description: value?.description ? String(value.description) : '',
  site_enabled: Boolean(value?.site_enabled),
  telegram_enabled: Boolean(value?.telegram_enabled),
  push_enabled:
    typeof value?.push_enabled === 'boolean'
      ? value.push_enabled
      : Boolean(value?.default_push_enabled),
  supports_grouping: Boolean(value?.supports_grouping),
  grouping_period: normalizeNotificationGroupingPeriod(value?.grouping_period),
  default_grouping_period: normalizeNotificationGroupingPeriod(value?.default_grouping_period),
  grouping_options: Array.isArray(value?.grouping_options)
    ? value.grouping_options
        .map((option: any) => ({
          value: normalizeNotificationGroupingPeriod(option?.value),
          label: String(option?.label || ''),
        }))
        .filter((option: { value: 'none' | 'day' | 'week'; label: string }) => option.label)
    : [],
  default_site_enabled: Boolean(value?.default_site_enabled),
  default_telegram_enabled: Boolean(value?.default_telegram_enabled),
  default_push_enabled:
    typeof value?.default_push_enabled === 'boolean'
      ? value.default_push_enabled
      : true,
})

const normalizeSiteAuthError = (message?: string | null, fallback = 'Не удалось выполнить вход') => {
  const value = String(message || '').trim().toLowerCase()
  if (!value) return fallback
  if (value === 'invalid credentials') {
    return 'Неверный логин, email или пароль. Проверьте данные и попробуйте снова.'
  }
  if (value === 'username and password are required') {
    return 'Введите email или имя пользователя и пароль.'
  }
  if (value === 'username, email and password are required') {
    return 'Введите имя пользователя, email и пароль.'
  }
  if (value === 'email already exists') {
    return 'Аккаунт с такой почтой уже существует.'
  }
  if (value === 'username already exists') {
    return 'Имя пользователя уже занято.'
  }
  return message as string
}

const parseApiResponse = async (response: Response) => {
  const raw = await response.text()
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw)
  } catch {
    throw new Error(
      `Сервер вернул HTML вместо JSON (${response.status}). Проверьте PUBLIC_BACKEND_URL и что backend запущен.`
    )
  }
}

const saveToken = (token: string | null) => {
  if (!browser) return
  localStorage.removeItem(TOKEN_KEY)
}

export const refreshSiteUser = async () => {
  const token = get(siteToken)

  const response = await fetch(buildUrl('/api/auth/me/'), {
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })

  if (!response.ok) {
    saveToken(null)
    resetBackendFeedSettingsSync()
    siteToken.set(null)
    siteUser.set(null)
    return null
  }

  const data = await parseApiResponse(response)
  if (data?.user) {
    if (!token) {
      siteToken.set(COOKIE_AUTH_SENTINEL)
    }
    siteUser.set(data.user)
    loadBackendFeedSettings(token || COOKIE_AUTH_SENTINEL).catch((error) => {
      console.error('Failed to load feed settings:', error)
    })
    return data.user as SiteUser
  }
  return null
}

let refreshSiteUserScheduled = false

export const scheduleRefreshSiteUser = () => {
  if (!browser || refreshSiteUserScheduled) return
  refreshSiteUserScheduled = true

  const run = () => {
    refreshSiteUser().catch((error) => {
      console.error('Failed to refresh site user:', error)
    })
  }

  if ('requestIdleCallback' in window) {
    window.requestIdleCallback(run, { timeout: 3000 })
    return
  }

  globalThis.setTimeout(run, 1500)
}

export const updateSiteProfile = async (payload: {
  display_name?: string
  avatar_url?: string | null
  email?: string | null
}) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl('/api/auth/me/'), {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  })

  const data = await parseApiResponse(response)
  if (!response.ok || !data?.user) {
    throw new Error(data?.error || 'Не удалось обновить профиль')
  }

  siteUser.set(data.user)
  return {
    user: data.user as SiteUser,
    emailVerificationSent: Boolean(data?.email_verification_sent),
  }
}

export const fetchStaticPageContent = async (slug: string) => {
  const response = await fetch(buildUrl(`/api/content-pages/${encodeURIComponent(slug)}/`), {
    cache: 'no-store',
    credentials: 'include',
  })
  const data = await parseApiResponse(response)
  if (!response.ok || !data?.page) {
    throw new Error(data?.error || 'Не удалось загрузить страницу')
  }
  return data.page as SiteStaticPageContent
}

export const updateStaticPageContent = async (slug: string, payload: {
  content: string
  title?: string
}) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl(`/api/content-pages/${encodeURIComponent(slug)}/`), {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  })

  const data = await parseApiResponse(response)
  if (!response.ok || !data?.page) {
    throw new Error(data?.error || 'Не удалось сохранить страницу')
  }
  return data.page as SiteStaticPageContent
}

export const login = async (username: string, password: string) => {
  const response = await fetch(buildUrl('/api/auth/login/'), {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })

  const data = await parseApiResponse(response)
  if (!response.ok || !data?.token) {
    throw new Error(normalizeSiteAuthError(data?.error, 'Не удалось войти'))
  }

  saveToken(data.token)
  siteToken.set(data.token)
  siteUser.set(data.user)
  loadBackendFeedSettings(data.token).catch((error) => {
    console.error('Failed to load feed settings:', error)
  })
  return data.user as SiteUser
}

export const register = async (payload: {
  username: string
  email: string
  password: string
  privacy_accepted?: boolean
  registration_source?: string
  registration_path?: string
}) => {
  const response = await fetch(buildUrl('/api/auth/register/'), {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  const data = await parseApiResponse(response)
  if (!response.ok || !data?.token) {
    throw new Error(data?.error || 'Не удалось зарегистрироваться')
  }

  saveToken(data.token)
  siteToken.set(data.token)
  siteUser.set(data.user)
  loadBackendFeedSettings(data.token).catch((error) => {
    console.error('Failed to load feed settings:', error)
  })
  return data.user as SiteUser
}

export const requestPasswordReset = async (email: string) => {
  const response = await fetch(buildUrl('/api/auth/password-reset/'), {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })

  const data = await parseApiResponse(response)
  if (!response.ok || !data?.ok) {
    throw new Error(normalizeSiteAuthError(data?.error, 'Не удалось отправить письмо'))
  }

  return true
}

export const verifyEmail = async (token: string, fetcher: typeof fetch = fetch) => {
  const response = await fetcher(`${buildUrl('/api/auth/verify-email/')}?token=${encodeURIComponent(token)}`, {
    method: 'GET',
    credentials: 'include',
  })

  const data = await parseApiResponse(response)
  if (!response.ok || !data?.ok) {
    throw new Error(normalizeSiteAuthError(data?.error, 'Не удалось подтвердить почту'))
  }

  if (data.user) {
    siteUser.set(data.user)
  }
  return data.user as SiteUser | undefined
}

export const confirmPasswordReset = async (payload: {
  uid: string
  token: string
  password: string
}) => {
  const response = await fetch(buildUrl('/api/auth/password-reset/confirm/'), {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  const data = await parseApiResponse(response)
  if (!response.ok || !data?.token) {
    throw new Error(normalizeSiteAuthError(data?.error, 'Не удалось обновить пароль'))
  }

  saveToken(data.token)
  siteToken.set(data.token)
  siteUser.set(data.user)
  loadBackendFeedSettings(data.token).catch((error) => {
    console.error('Failed to load feed settings:', error)
  })
  return data.user as SiteUser
}

export type TelegramAuthPayload = {
  auth_intent?: 'login' | 'signup'
  id_token?: string
  id?: number
  first_name?: string
  last_name?: string
  username?: string
  photo_url?: string
  auth_date?: number
  hash?: string
  phone?: string
  phone_number?: string
  privacy_accepted?: boolean
  registration_source?: string
  registration_path?: string
}

export const loginTelegram = async (payload: TelegramAuthPayload) => {
  const token = get(siteToken)
  const response = await fetch(buildUrl('/api/auth/telegram/'), {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  })

  const data = await parseApiResponse(response)
  if (!response.ok || !data?.token) {
    throw new Error(data?.error || 'Не удалось войти через Telegram')
  }

  saveToken(data.token)
  siteToken.set(data.token)
  siteUser.set(data.user)
  loadBackendFeedSettings(data.token).catch((error) => {
    console.error('Failed to load feed settings:', error)
  })
  return data.user as SiteUser
}

export type VkAuthPayload = {
  auth_intent?: 'login' | 'signup'
  access_token: string
  expires_in?: number
  user_id?: number
  id_token?: string
  email?: string
  phone?: string
  privacy_accepted?: boolean
  registration_source?: string
  registration_path?: string
}

export const loginVK = async (payload: VkAuthPayload) => {
  const token = get(siteToken)
  const response = await fetch(buildUrl('/api/auth/vk/'), {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  })

  const data = await parseApiResponse(response)
  if (!response.ok || !data?.token) {
    throw new Error(data?.error || 'Не удалось войти через VK')
  }

  saveToken(data.token)
  siteToken.set(data.token)
  siteUser.set(data.user)
  loadBackendFeedSettings(data.token).catch((error) => {
    console.error('Failed to load feed settings:', error)
  })
  return data.user as SiteUser
}

export const logout = () => {
  const token = get(siteToken)
  fetch(buildUrl('/api/auth/logout/'), {
    method: 'POST',
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  }).catch((error) => {
    console.error('Failed to revoke auth token:', error)
  })
  saveToken(null)
  resetBackendFeedSettingsSync()
  siteToken.set(null)
  siteUser.set(null)
}

export const deleteSiteAccount = async () => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl('/api/auth/me/'), {
    method: 'DELETE',
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  const data = await parseApiResponse(response)
  if (!response.ok || !data?.ok) {
    throw new Error(data?.error || 'Не удалось удалить профиль')
  }

  saveToken(null)
  resetBackendFeedSettingsSync()
  siteToken.set(null)
  siteUser.set(null)
  return true
}

export const fetchVerificationCode = async () => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl('/api/auth/verification-code/'), {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  })

  const data = await response.json()
  if (!response.ok || !data?.code) {
    throw new Error(data?.error || 'Не удалось получить код')
  }

  return data.code as string
}

export const fetchUserPosts = async (limit = 20, offset = 0) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })

  const response = await fetch(buildUrl(`/api/auth/posts/?${params.toString()}`), {
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data?.error || 'Не удалось загрузить посты')
  }

  return {
    posts: (data?.posts || []) as SiteUserPost[],
    total: data?.total ?? 0,
  }
}

export const fetchUserPost = async (postId: number) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl(`/api/auth/posts/${postId}/`), {
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  const data = await response.json()
  if (!response.ok || !data?.post) {
    throw new Error(data?.error || 'Не удалось загрузить пост')
  }

  return data.post as SiteUserPost
}

export const updateUserPost = async (
  postId: number,
  payload: {
    title?: string
    content?: string
    author_source?: 'site'
    author_username?: string
    comun_slug?: string
    comun_category_id?: number | null
    is_draft?: boolean
    tags?: string[]
    template?: SitePostTemplate | null
  },
  options?: {
    keepalive?: boolean
  }
) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl(`/api/auth/posts/${postId}/`), {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    keepalive: options?.keepalive,
    body: JSON.stringify(payload),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data?.error || 'Не удалось обновить пост')
  }

  return data?.post as SiteUserPost
}

export const deleteUserPost = async (postId: number) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl(`/api/auth/posts/${postId}/`), {
    method: 'DELETE',
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data?.error || 'Не удалось удалить пост')
  }

  return data
}

export const createUserPost = async (payload: {
  title?: string
  content?: string
  author_source?: 'site'
  author_username?: string
  comun_slug?: string
  comun_category_id?: number | null
  is_draft?: boolean
  tags?: string[]
  template?: SitePostTemplate | null
}, options?: {
  keepalive?: boolean
}) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl('/api/auth/posts/'), {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    keepalive: options?.keepalive,
    body: JSON.stringify(payload),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data?.error || 'Не удалось создать пост')
  }

  return data?.post as SiteUserPost
}

export const fetchSharedDraft = async (shareToken: string) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(
    buildUrl(`/api/auth/drafts/shared/${encodeURIComponent(shareToken)}/`),
    {
      credentials: 'include',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  )

  const data = await response.json().catch(() => null)
  if (!response.ok || !data?.post) {
    throw new Error(data?.error || 'Не удалось загрузить черновик')
  }

  return data.post as SiteUserPost
}

export const createComunPost = async (
  comunSlug: string,
  payload: {
    title: string
    content: string
    author_source?: 'site'
    author_username?: string
    comun_category_id?: number | null
    tags?: string[]
    template?: SitePostTemplate | null
  }
) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(
    buildUrl(`/api/comuns/${encodeURIComponent(comunSlug)}/posts/`),
    {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    }
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data?.error || 'Не удалось создать пост в комуне')
  }

  return data?.post as SiteUserPost
}

export const uploadSiteImage = async (image: File) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }
  const maxBytes = 10 * 1024 * 1024
  if (image.size > maxBytes) {
    throw new Error('Файл слишком большой (максимум 10 МБ)')
  }
  const normalizedType = String(image.type || '').toLowerCase()
  if (normalizedType && !['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(normalizedType)) {
    throw new Error('Неподдерживаемый формат файла. Допустимы JPG, PNG, WEBP и GIF')
  }
  const formData = new FormData()
  formData.append('image', image)

  const response = await fetch(buildUrl('/api/auth/uploads/'), {
    method: 'POST',
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  })

  const contentType = (response.headers.get('content-type') || '').toLowerCase()
  let data: any = null
  if (contentType.includes('application/json')) {
    data = await response.json()
  } else {
    const text = await response.text()
    if (!response.ok) {
      const normalizedText = text.toLowerCase()
      if (
        response.status === 413 ||
        normalizedText.includes('requestdatatoobig') ||
        normalizedText.includes('too large')
      ) {
        throw new Error('Файл слишком большой (максимум 10 МБ)')
      }
      throw new Error('Сервер вернул некорректный ответ при загрузке изображения')
    }
    throw new Error('Сервер вернул некорректный ответ при загрузке изображения')
  }
  if (!response.ok || !data?.url) {
    const errorMessage = String(data?.error || '').toLowerCase()
    if (errorMessage.includes('too large')) {
      throw new Error('Файл слишком большой (максимум 10 МБ)')
    }
    if (errorMessage.includes('unsupported file type')) {
      throw new Error('Неподдерживаемый формат файла. Допустимы JPG, PNG, WEBP и GIF')
    }
    if (errorMessage.includes('invalid image file')) {
      throw new Error('Файл поврежден или не является корректным изображением')
    }
    throw new Error(data?.error || 'Не удалось загрузить изображение')
  }
  return data.url as string
}

export const autofillMovieReviewTemplateByImdb = async (imdbUrl: string) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }
  const response = await fetch(buildUrl('/api/auth/post-templates/movie-review/autofill/'), {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ imdb_url: imdbUrl }),
  })

  const data = await response.json().catch(() => null)
  if (!response.ok || !data?.template?.data) {
    throw new Error(data?.error || 'Не удалось получить данные фильма')
  }
  return {
    imdb_id: String(data?.imdb_id || ''),
    data: (data?.template?.data || {}) as Partial<MovieReviewTemplateData>,
    sources: Array.isArray(data?.sources) ? data.sources.map((item: unknown) => String(item)) : [],
    warnings: Array.isArray(data?.warnings) ? data.warnings.map((item: unknown) => String(item)) : [],
  }
}

const parsePostIdFromReference = (value: string): number | null => {
  const raw = (value || '').trim()
  if (!raw) return null
  if (/^\d+$/.test(raw)) {
    const numericId = Number(raw)
    return Number.isFinite(numericId) && numericId > 0 ? numericId : null
  }
  const match = raw.match(/\/b\/post\/(\d+)/)
  if (!match) return null
  const numericId = Number(match[1])
  return Number.isFinite(numericId) && numericId > 0 ? numericId : null
}

const normalizeVotePollCandidate = (
  value: any,
  fallbackPostId?: number | null
): VotePollPostCandidate | null => {
  const postIdRaw = Number(value?.post_id ?? value?.id ?? fallbackPostId ?? 0)
  const postId = Number.isFinite(postIdRaw) ? Math.floor(postIdRaw) : 0
  if (postId <= 0) return null
  const title = String(value?.title ?? value?.name ?? '').trim() || `Пост #${postId}`
  const path = buildBackendPostPath({ id: postId, title })
  const authorUsername = String(value?.author?.username ?? value?.author_username ?? '').trim()
  return {
    post_id: postId,
    title,
    path,
    ...(authorUsername ? { author_username: authorUsername } : {}),
  }
}

export const resolveVotePollPostByReference = async (
  reference: string
): Promise<VotePollPostCandidate> => {
  const postId = parsePostIdFromReference(reference)
  if (!postId) {
    throw new Error('Некорректная ссылка на пост')
  }
  const response = await fetch(buildPostDetailUrl(postId), {
    credentials: 'include',
    headers: {
      ...(get(siteToken) ? { Authorization: `Bearer ${get(siteToken)}` } : {}),
    },
  })
  const data = await response.json().catch(() => null)
  if (!response.ok || !data?.post) {
    throw new Error(data?.error || 'Пост не найден')
  }
  const candidate = normalizeVotePollCandidate(data.post, postId)
  if (!candidate) {
    throw new Error('Пост не найден')
  }
  return candidate
}

export const searchPostsForVotePoll = async (
  query: string,
  limit = 10
): Promise<VotePollPostCandidate[]> => {
  const normalizedQuery = query.trim()
  if (!normalizedQuery) return []

  const safeLimit = Math.min(Math.max(limit, 1), 20)
  const response = await fetch(buildSearchUrl(normalizedQuery, 1, safeLimit, 'Posts', 'New'), {
    credentials: 'include',
    headers: {
      ...(get(siteToken) ? { Authorization: `Bearer ${get(siteToken)}` } : {}),
    },
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(data?.error || 'Не удалось выполнить поиск постов')
  }
  const source = Array.isArray(data?.posts) ? data.posts : []
  const normalized: VotePollPostCandidate[] = []
  const seen = new Set<number>()
  for (const item of source) {
    const candidate = normalizeVotePollCandidate(item)
    if (!candidate) continue
    if (seen.has(candidate.post_id)) continue
    seen.add(candidate.post_id)
    normalized.push(candidate)
    if (normalized.length >= 10) break
  }
  return normalized
}

export const fetchSiteNotifications = async (
  limit = 10,
  unreadOnly = false,
  offset = 0
) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(Math.max(0, offset)),
  })
  if (unreadOnly) {
    params.set('unread_only', '1')
  }

  const response = await fetch(buildUrl(`/api/auth/notifications/?${params.toString()}`), {
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data?.error || 'Не удалось загрузить уведомления')
  }

  return {
    items: (data?.items || []) as SiteNotificationItem[],
    unread_count: Number(data?.unread_count || 0),
    total_count: Number(data?.total_count || 0),
  }
}

export const markSiteNotificationRead = async (notificationId: number) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl(`/api/auth/notifications/${notificationId}/read/`), {
    method: 'POST',
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data?.error || 'Не удалось отметить уведомление')
  }

  return {
    item: data?.item as SiteNotificationItem,
    unread_count: Number(data?.unread_count || 0),
  }
}

export const markAllSiteNotificationsRead = async () => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl('/api/auth/notifications/read-all/'), {
    method: 'POST',
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data?.error || 'Не удалось отметить все уведомления')
  }

  return {
    updated: Number(data?.updated || 0),
    unread_count: Number(data?.unread_count || 0),
  }
}

export const fetchSiteChats = async (limit = 50, offset = 0): Promise<SiteChatListResponse> => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }
  const response = await fetch(buildAuthChatsUrl({ limit, offset }), {
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
  const data = await response.json()
  if (!response.ok) {
    throw new Error(data?.error || 'Не удалось загрузить чаты')
  }
  return {
    chats: (data?.chats || []) as BackendSiteChat[],
    total: Number(data?.total || 0),
    limit: Number(data?.limit || limit),
    offset: Number(data?.offset || offset),
  }
}

export const createSiteChat = async (participantId: number): Promise<BackendSiteChat> => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }
  const response = await fetch(buildAuthChatsUrl(), {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ participant_id: participantId }),
  })
  const data = await response.json()
  if (!response.ok || !data?.chat) {
    throw new Error(data?.error || 'Не удалось открыть чат')
  }
  return data.chat as BackendSiteChat
}

export const fetchSiteChat = async (
  chatId: number,
  limit = 50,
  beforeId?: number
): Promise<SiteChatDetailResponse> => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }
  const response = await fetch(buildAuthChatUrl(chatId, { limit, beforeId }), {
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
  const data = await response.json()
  if (!response.ok || !data?.chat) {
    throw new Error(data?.error || 'Не удалось загрузить чат')
  }
  return {
    chat: data.chat as BackendSiteChat,
    messages: (data?.messages || []) as BackendSiteChatMessage[],
  }
}

export const sendSiteChatMessage = async (
  chatId: number,
  body: string
): Promise<{ chat: BackendSiteChat; message: BackendSiteChatMessage }> => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }
  const response = await fetch(buildAuthChatMessagesUrl(chatId), {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ body }),
  })
  const data = await response.json()
  if (!response.ok || !data?.message || !data?.chat) {
    throw new Error(data?.error || 'Не удалось отправить сообщение')
  }
  return {
    chat: data.chat as BackendSiteChat,
    message: data.message as BackendSiteChatMessage,
  }
}

export const reportAndBlockSiteChat = async (
  chatId: number
): Promise<{ blocked: boolean; report: BackendSiteChatReport }> => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }
  const response = await fetch(buildAuthChatReportBlockUrl(chatId), {
    method: 'POST',
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
  const data = await response.json()
  if (!response.ok || !data?.report) {
    throw new Error(data?.error || 'Не удалось заблокировать чат')
  }
  return {
    blocked: Boolean(data?.blocked),
    report: data.report as BackendSiteChatReport,
  }
}

export const fetchSiteNotificationSettings = async (): Promise<SiteNotificationSettingsResponse> => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl('/api/auth/notifications/settings/'), {
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data?.error || 'Не удалось загрузить настройки оповещений')
  }

  return {
    events: Array.isArray(data?.events)
      ? data.events.map(normalizeSiteNotificationEventSetting)
      : [],
    telegram: {
      linked: Boolean(data?.telegram?.linked),
      username: data?.telegram?.username ?? '',
      first_name: data?.telegram?.first_name ?? '',
    },
    push: {
      configured: Boolean(data?.push?.configured),
      registered_devices_count: Number(data?.push?.registered_devices_count || 0),
      active_platforms: Array.isArray(data?.push?.active_platforms)
        ? (data.push.active_platforms as string[])
        : [],
    },
  }
}

export const updateSiteNotificationSettings = async (
  events: Array<{
    key: string
    site_enabled: boolean
    telegram_enabled: boolean
    push_enabled: boolean
    grouping_period?: 'none' | 'day' | 'week'
  }>
): Promise<SiteNotificationSettingsResponse> => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl('/api/auth/notifications/settings/'), {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ events }),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data?.error || 'Не удалось сохранить настройки оповещений')
  }

  return {
    events: Array.isArray(data?.events)
      ? data.events.map(normalizeSiteNotificationEventSetting)
      : [],
    telegram: {
      linked: Boolean(data?.telegram?.linked),
      username: data?.telegram?.username ?? '',
      first_name: data?.telegram?.first_name ?? '',
    },
    push: {
      configured: Boolean(data?.push?.configured),
      registered_devices_count: Number(data?.push?.registered_devices_count || 0),
      active_platforms: Array.isArray(data?.push?.active_platforms)
        ? (data.push.active_platforms as string[])
        : [],
    },
  }
}

if (browser) {
  saveToken(null)
  scheduleRefreshSiteUser()
}
