const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f-\u009f]/g

export type SafeUrlOptions = {
  allowRelative?: boolean
  allowedProtocols?: string[]
  allowDataImage?: boolean
}

const normalizeProtocol = (protocol: string) => protocol.trim().toLowerCase()

export const getSafeUrl = (
  value: unknown,
  {
    allowRelative = true,
    allowedProtocols = ['http:', 'https:'],
    allowDataImage = false,
  }: SafeUrlOptions = {}
) => {
  const raw = String(value ?? '').trim().replace(CONTROL_CHARACTERS, '')
  if (!raw) return null

  const compact = raw.replace(/\s+/g, '')
  if (allowDataImage && /^data:image\/(?:png|jpe?g|gif|webp);base64,[a-z0-9+/]+=*$/i.test(compact)) {
    return compact
  }

  const protocolMatch = compact.match(/^([a-z0-9+.-]+):/i)
  if (protocolMatch) {
    const protocol = `${normalizeProtocol(protocolMatch[1])}:`
    return allowedProtocols.map(normalizeProtocol).includes(protocol) ? raw : null
  }

  if (raw.startsWith('//')) {
    try {
      const url = new URL(`https:${raw}`)
      return allowedProtocols.map(normalizeProtocol).includes(url.protocol) ? raw : null
    } catch {
      return null
    }
  }

  return allowRelative ? raw : null
}

export const isSafeUrl = (value: unknown, options?: SafeUrlOptions) => getSafeUrl(value, options) !== null
