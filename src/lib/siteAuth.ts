import { browser } from '$app/environment'
import { getBackendBaseUrl } from '$lib/api/backend'
import { writable, get } from 'svelte/store'

export type SiteAuthorLink = {
  username: string
  title?: string | null
  channel_url?: string | null
}

export type SiteUser = {
  id: number
  username: string
  email?: string | null
  is_author: boolean
  authors: SiteAuthorLink[]
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

if (browser && initialToken) {
  refreshSiteUser()
}
