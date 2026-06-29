const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f-\u009f]/g

export type SafeUrlOptions = {
  allowRelative?: boolean
  allowedProtocols?: string[]
  allowDataImage?: boolean
  normalizeBareExternal?: boolean
}

const normalizeProtocol = (protocol: string) => protocol.trim().toLowerCase()
const BARE_EXTERNAL_URL =
  /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}(?::\d{1,5})?(?:[/?#].*)?$/i
const RELATIVE_URL_PREFIX = /^(?:[/?#]|\.{1,2}\/)/

export const isBareExternalUrl = (value: unknown) => {
  const raw = String(value ?? '').trim().replace(CONTROL_CHARACTERS, '')
  if (!raw || /\s/.test(raw)) return false
  if (RELATIVE_URL_PREFIX.test(raw)) return false
  if (/^[a-z0-9+.-]+:/i.test(raw)) return false
  if (raw.startsWith('//')) return false
  return BARE_EXTERNAL_URL.test(raw)
}

export const getSafeUrl = (
  value: unknown,
  {
    allowRelative = true,
    allowedProtocols = ['http:', 'https:'],
    allowDataImage = false,
    normalizeBareExternal = false,
  }: SafeUrlOptions = {}
) => {
  const raw = String(value ?? '').trim().replace(CONTROL_CHARACTERS, '')
  if (!raw) return null
  const normalizedAllowedProtocols = allowedProtocols.map(normalizeProtocol)

  const compact = raw.replace(/\s+/g, '')
  if (allowDataImage && /^data:image\/(?:png|jpe?g|gif|webp);base64,[a-z0-9+/]+=*$/i.test(compact)) {
    return compact
  }

  const protocolMatch = compact.match(/^([a-z0-9+.-]+):/i)
  if (protocolMatch) {
    const protocol = `${normalizeProtocol(protocolMatch[1])}:`
    return normalizedAllowedProtocols.includes(protocol) ? raw : null
  }

  if (raw.startsWith('//')) {
    try {
      const url = new URL(`https:${raw}`)
      return normalizedAllowedProtocols.includes(url.protocol) ? raw : null
    } catch {
      return null
    }
  }

  if (normalizeBareExternal && isBareExternalUrl(raw)) {
    return normalizedAllowedProtocols.includes('https:') ? `https://${raw}` : null
  }

  return allowRelative ? raw : null
}

export const isSafeUrl = (value: unknown, options?: SafeUrlOptions) => getSafeUrl(value, options) !== null

export const isExternalUrl = (value: unknown) => {
  const safeUrl = getSafeUrl(value, {
    allowedProtocols: ['http:', 'https:', 'mailto:'],
    allowRelative: true,
    normalizeBareExternal: true,
  })
  return Boolean(safeUrl && (/^(?:https?:)?\/\//i.test(safeUrl) || /^mailto:/i.test(safeUrl)))
}
