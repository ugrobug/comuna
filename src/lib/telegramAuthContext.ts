import { browser } from '$app/environment'

export const TELEGRAM_AUTH_COMPLETE_EVENT = 'tambur:telegram-auth-complete'

const TELEGRAM_AUTH_CONTEXT_KEY = 'tambur.telegramAuthContext'
const TELEGRAM_AUTH_CONTEXT_TTL_MS = 10 * 60 * 1000

export type TelegramAuthIntent = 'login' | 'signup'

export type TelegramAuthContext = {
  authIntent: TelegramAuthIntent
  privacyAccepted: boolean
  returnTo: string
  registrationSource?: string
  registrationPath?: string
  createdAt: number
}

const normalizeReturnTo = (value: string | null | undefined) => {
  const fallback = '/'
  const next = String(value || '').trim()
  if (!next || !next.startsWith('/') || next.startsWith('//')) return fallback
  if (next.startsWith('/auth/telegram/callback')) return fallback
  return next
}

export const defaultTelegramAuthContext = (): TelegramAuthContext => ({
  authIntent: 'login',
  privacyAccepted: false,
  returnTo: '/',
  createdAt: Date.now(),
})

export const rememberTelegramAuthContext = (context: Omit<TelegramAuthContext, 'createdAt'>) => {
  if (!browser) return
  localStorage.setItem(
    TELEGRAM_AUTH_CONTEXT_KEY,
    JSON.stringify({
      authIntent: context.authIntent === 'signup' ? 'signup' : 'login',
      privacyAccepted: Boolean(context.privacyAccepted),
      returnTo: normalizeReturnTo(context.returnTo),
      registrationSource: String(context.registrationSource || '').trim(),
      registrationPath: String(context.registrationPath || '').trim(),
      createdAt: Date.now(),
    }),
  )
}

export const forgetTelegramAuthContext = () => {
  if (!browser) return
  localStorage.removeItem(TELEGRAM_AUTH_CONTEXT_KEY)
}

export const consumeTelegramAuthContext = (): TelegramAuthContext => {
  if (!browser) return defaultTelegramAuthContext()

  const fallback = defaultTelegramAuthContext()
  const raw = localStorage.getItem(TELEGRAM_AUTH_CONTEXT_KEY)
  localStorage.removeItem(TELEGRAM_AUTH_CONTEXT_KEY)
  if (!raw) return fallback

  try {
    const parsed = JSON.parse(raw)
    const createdAt = Number(parsed?.createdAt || 0)
    if (!createdAt || Date.now() - createdAt > TELEGRAM_AUTH_CONTEXT_TTL_MS) {
      return fallback
    }
    return {
      authIntent: parsed?.authIntent === 'signup' ? 'signup' : 'login',
      privacyAccepted: Boolean(parsed?.privacyAccepted),
      returnTo: normalizeReturnTo(parsed?.returnTo),
      registrationSource: String(parsed?.registrationSource || '').trim(),
      registrationPath: String(parsed?.registrationPath || '').trim(),
      createdAt,
    }
  } catch {
    return fallback
  }
}
