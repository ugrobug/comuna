export type DzenUrlMatch = {
  href: string
  source: string
}

const trimTrailingPunctuation = (value: string): string =>
  value.replace(/[\]\[(){},.!?;:]+$/u, '')

export const isDzenUrl = (value: string): boolean => {
  const candidate = value.trim()
  if (!candidate) return false

  try {
    const url = new URL(/^https?:\/\//i.test(candidate) ? candidate : `https://${candidate}`)
    const hostname = url.hostname.toLowerCase().replace(/^www\./, '')
    if (hostname === 'dzen.ru' || hostname.endsWith('.dzen.ru')) return true
    if (hostname.startsWith('zen.yandex.')) return true
    return /^yandex\.[a-z.]+$/i.test(hostname) && /^\/zen(?:\/|$)/i.test(url.pathname)
  } catch {
    return false
  }
}

export const findDzenUrl = (value: string): DzenUrlMatch | null => {
  const text = String(value ?? '')
  const candidates = text.match(/(?:https?:\/\/)?[^\s<>"']+/giu) ?? []
  for (const rawCandidate of candidates) {
    const source = trimTrailingPunctuation(rawCandidate)
    if (!isDzenUrl(source)) continue
    return {
      href: /^https?:\/\//i.test(source) ? source : `https://${source}`,
      source,
    }
  }
  return null
}
