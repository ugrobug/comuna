import { browser } from '$app/environment'
import {
  buildBackendPostPath,
  buildPostDetailUrl,
  buildSearchUrl,
  getBackendBaseUrl,
} from '$lib/api/backend'
import type {
  MovieReviewTemplateData,
  PostVotePollTemplateItem,
  SitePostTemplate,
} from '$lib/postTemplates'
import { writable, get } from 'svelte/store'

export type SiteAuthorLink = {
  username: string
  title?: string | null
  channel_url?: string | null
  avatar_url?: string | null
  rubric?: string | null
  rubric_slug?: string | null
  auto_publish?: boolean
  publish_delay_days?: number
  notify_comments?: boolean
  invite_url?: string | null
  author_rating?: number
}

export type SiteUser = {
  id: number
  username: string
  display_name?: string | null
  email?: string | null
  avatar_url?: string | null
  is_staff?: boolean
  is_author: boolean
  authors: SiteAuthorLink[]
}

export type SiteUserPost = {
  id: number
  title: string
  content: string
  template?: SitePostTemplate | null
  created_at: string
  updated_at?: string
  is_pending?: boolean
  is_draft?: boolean
  draft_share_token?: string | null
  publish_at?: string | null
  rubric?: string | null
  rubric_slug?: string | null
  rubric_icon_url?: string | null
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
  is_read: boolean
  read_at?: string | null
  created_at: string
}

export type SiteNotificationEventSetting = {
  key: string
  title: string
  description?: string
  site_enabled: boolean
  telegram_enabled: boolean
  default_site_enabled: boolean
  default_telegram_enabled: boolean
}

export type SiteNotificationSettingsResponse = {
  events: SiteNotificationEventSetting[]
  telegram: {
    linked: boolean
    username?: string | null
    first_name?: string | null
  }
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

const initialToken = browser ? localStorage.getItem(TOKEN_KEY) : null

export const siteToken = writable<string | null>(initialToken)
export const siteUser = writable<SiteUser | null>(null)

const buildUrl = (path: string) => `${getBackendBaseUrl()}${path}`

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
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

export const refreshSiteUser = async () => {
  const token = get(siteToken)
  if (!token) {
    siteUser.set(null)
    return null
  }

  const response = await fetch(buildUrl('/api/auth/me/'), {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  if (!response.ok) {
    saveToken(null)
    siteToken.set(null)
    siteUser.set(null)
    return null
  }

  const data = await parseApiResponse(response)
  if (data?.user) {
    siteUser.set(data.user)
    return data.user as SiteUser
  }
  return null
}

export const updateSiteProfile = async (payload: {
  display_name?: string
  avatar_url?: string | null
}) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl('/api/auth/me/'), {
    method: 'PATCH',
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
  return data.user as SiteUser
}

export const fetchStaticPageContent = async (slug: string) => {
  const response = await fetch(buildUrl(`/api/content-pages/${encodeURIComponent(slug)}/`), {
    cache: 'no-store',
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })

  const data = await parseApiResponse(response)
  if (!response.ok || !data?.token) {
    throw new Error(data?.error || 'Не удалось войти')
  }

  saveToken(data.token)
  siteToken.set(data.token)
  siteUser.set(data.user)
  return data.user as SiteUser
}

export const register = async (payload: {
  username: string
  email?: string
  password: string
}) => {
  const response = await fetch(buildUrl('/api/auth/register/'), {
    method: 'POST',
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
  return data.user as SiteUser
}

export type TelegramAuthPayload = {
  id: number
  first_name?: string
  last_name?: string
  username?: string
  photo_url?: string
  auth_date: number
  hash: string
}

export const loginTelegram = async (payload: TelegramAuthPayload) => {
  const response = await fetch(buildUrl('/api/auth/telegram/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  const data = await parseApiResponse(response)
  if (!response.ok || !data?.token) {
    throw new Error(data?.error || 'Не удалось войти через Telegram')
  }

  saveToken(data.token)
  siteToken.set(data.token)
  siteUser.set(data.user)
  return data.user as SiteUser
}

export type VkAuthPayload = {
  access_token: string
  expires_in?: number
  user_id?: number
  id_token?: string
}

export const loginVK = async (payload: VkAuthPayload) => {
  const response = await fetch(buildUrl('/api/auth/vk/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  const data = await parseApiResponse(response)
  if (!response.ok || !data?.token) {
    throw new Error(data?.error || 'Не удалось войти через VK')
  }

  saveToken(data.token)
  siteToken.set(data.token)
  siteUser.set(data.user)
  return data.user as SiteUser
}

export const logout = () => {
  saveToken(null)
  siteToken.set(null)
  siteUser.set(null)
}

export const fetchVerificationCode = async () => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl('/api/auth/verification-code/'), {
    method: 'POST',
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
    rubric_slug?: string
    is_draft?: boolean
    tags?: string[]
    template?: SitePostTemplate | null
  }
) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl(`/api/auth/posts/${postId}/`), {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
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
  rubric_slug?: string
  is_draft?: boolean
  tags?: string[]
  template?: SitePostTemplate | null
}) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl('/api/auth/posts/'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
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
  const formData = new FormData()
  formData.append('image', image)

  const response = await fetch(buildUrl('/api/auth/uploads/'), {
    method: 'POST',
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
    await response.text()
    if (!response.ok) {
      if (response.status === 413) {
        throw new Error('Файл слишком большой (максимум 10 МБ)')
      }
      throw new Error('Сервер вернул некорректный ответ при загрузке изображения')
    }
    throw new Error('Сервер вернул некорректный ответ при загрузке изображения')
  }
  if (!response.ok || !data?.url) {
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

export const fetchSiteNotifications = async (limit = 10, unreadOnly = false) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const params = new URLSearchParams({ limit: String(limit) })
  if (unreadOnly) {
    params.set('unread_only', '1')
  }

  const response = await fetch(buildUrl(`/api/auth/notifications/?${params.toString()}`), {
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
  }
}

export const markSiteNotificationRead = async (notificationId: number) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl(`/api/auth/notifications/${notificationId}/read/`), {
    method: 'POST',
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

export const fetchSiteNotificationSettings = async (): Promise<SiteNotificationSettingsResponse> => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl('/api/auth/notifications/settings/'), {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data?.error || 'Не удалось загрузить настройки оповещений')
  }

  return {
    events: (data?.events || []) as SiteNotificationEventSetting[],
    telegram: {
      linked: Boolean(data?.telegram?.linked),
      username: data?.telegram?.username ?? '',
      first_name: data?.telegram?.first_name ?? '',
    },
  }
}

export const updateSiteNotificationSettings = async (
  events: Array<{
    key: string
    site_enabled: boolean
    telegram_enabled: boolean
  }>
): Promise<SiteNotificationSettingsResponse> => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
  }

  const response = await fetch(buildUrl('/api/auth/notifications/settings/'), {
    method: 'PATCH',
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
    events: (data?.events || []) as SiteNotificationEventSetting[],
    telegram: {
      linked: Boolean(data?.telegram?.linked),
      username: data?.telegram?.username ?? '',
      first_name: data?.telegram?.first_name ?? '',
    },
  }
}

if (browser && initialToken) {
  refreshSiteUser()
}
