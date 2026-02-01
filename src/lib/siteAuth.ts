import { browser } from '$app/environment'
import { getBackendBaseUrl } from '$lib/api/backend'
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
  invite_url?: string | null
}

export type SiteUser = {
  id: number
  username: string
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
  created_at: string
  updated_at?: string
  is_pending?: boolean
  publish_at?: string | null
  rubric?: string | null
  rubric_slug?: string | null
  rubric_icon_url?: string | null
  tags?: string[]
  author: {
    username: string
    title?: string | null
    avatar_url?: string | null
  }
}

const TOKEN_KEY = 'comuna.site.token'

const initialToken = browser ? localStorage.getItem(TOKEN_KEY) : null

export const siteToken = writable<string | null>(initialToken)
export const siteUser = writable<SiteUser | null>(null)

const buildUrl = (path: string) => `${getBackendBaseUrl()}${path}`

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

  const data = await response.json()
  if (data?.user) {
    siteUser.set(data.user)
    return data.user as SiteUser
  }
  return null
}

export const login = async (username: string, password: string) => {
  const response = await fetch(buildUrl('/api/auth/login/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })

  const data = await response.json()
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

  const data = await response.json()
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

  const data = await response.json()
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

  const data = await response.json()
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

export const updateUserPost = async (
  postId: number,
  payload: { title?: string; content?: string }
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

export const createUserPost = async (payload: {
  title: string
  content: string
  author_username?: string
  rubric_slug?: string
  tags?: string[]
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

export const uploadSiteImage = async (image: File) => {
  const token = get(siteToken)
  if (!token) {
    throw new Error('Нужна авторизация')
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

  const data = await response.json()
  if (!response.ok || !data?.url) {
    throw new Error(data?.error || 'Не удалось загрузить изображение')
  }
  return data.url as string
}

if (browser && initialToken) {
  refreshSiteUser()
}
