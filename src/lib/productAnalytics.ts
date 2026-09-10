export const PRODUCT_EVENTS = [
  'signup_completed',
  'meaningful_read',
  'community_subscribed',
  'community_unsubscribed',
  'comment_created',
  'vote_created',
  'post_published',
] as const

export type ProductEvent = (typeof PRODUCT_EVENTS)[number]
export type ProductEventParams = Record<string, string | number | boolean | null | undefined>

const DEFAULT_COUNTER_ID = 106046128
const VALUABLE_EVENTS = new Set<ProductEvent>([
  'signup_completed',
  'meaningful_read',
  'community_subscribed',
  'comment_created',
  'vote_created',
  'post_published',
])

export const sanitizeEventParams = (params: ProductEventParams = {}) =>
  Object.fromEntries(
    Object.entries(params)
      .filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value))
      .map(([key, value]) => [
        key.slice(0, 80),
        typeof value === 'string' ? value.slice(0, 200) : value,
      ])
  )

export const trackProductEvent = (
  event: ProductEvent,
  params: ProductEventParams = {}
) => {
  if (typeof window === 'undefined' || typeof window.ym !== 'function') return false
  const counterId = Number(window.__TAMBUR_YM_COUNTER_ID__ || DEFAULT_COUNTER_ID)
  const safeParams = sanitizeEventParams(params)
  window.ym(counterId, 'reachGoal', event, safeParams)
  if (VALUABLE_EVENTS.has(event)) {
    window.ym(counterId, 'reachGoal', 'valuable_action', {
      ...safeParams,
      action: event,
    })
  }
  return true
}

export const isPostPath = (pathname: string) =>
  /^\/(?:[a-z]{2}\/)?(?:b\/)?post\//.test(pathname)

export const shouldTrackMeaningfulRead = (
  activeSeconds: number,
  scrollProgress: number
) => activeSeconds >= 60 && scrollProgress >= 0.7

export const startMeaningfulReadTracking = (pathname: string) => {
  if (typeof window === 'undefined' || typeof document === 'undefined' || !isPostPath(pathname)) {
    return () => undefined
  }

  let activeSeconds = 0
  let maximumScrollProgress = 0
  let sent = false

  const updateScrollProgress = () => {
    const documentHeight = Math.max(
      document.documentElement.scrollHeight,
      document.body?.scrollHeight || 0,
      window.innerHeight
    )
    maximumScrollProgress = Math.max(
      maximumScrollProgress,
      Math.min(1, (window.scrollY + window.innerHeight) / documentHeight)
    )
  }

  const maybeTrack = () => {
    if (sent || !shouldTrackMeaningfulRead(activeSeconds, maximumScrollProgress)) return
    sent = true
    trackProductEvent('meaningful_read', {
      active_seconds: activeSeconds,
      scroll_percent: Math.round(maximumScrollProgress * 100),
    })
  }

  updateScrollProgress()
  const timer = window.setInterval(() => {
    if (!document.hidden && document.hasFocus()) activeSeconds += 1
    updateScrollProgress()
    maybeTrack()
  }, 1000)
  window.addEventListener('scroll', updateScrollProgress, { passive: true })

  return () => {
    window.clearInterval(timer)
    window.removeEventListener('scroll', updateScrollProgress)
  }
}
