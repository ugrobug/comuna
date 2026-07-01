export const originalPostLanguage = 'ru'

export const translatedPostLanguages = ['en', 'es', 'pt', 'de', 'fr', 'tr', 'id'] as const

export const postLanguageCodes = [originalPostLanguage, ...translatedPostLanguages] as const

export type PostLanguageCode = (typeof postLanguageCodes)[number]

export const postLanguageLocales: Record<PostLanguageCode, string> = {
  ru: 'ru-RU',
  en: 'en',
  es: 'es',
  pt: 'pt',
  de: 'de',
  fr: 'fr',
  tr: 'tr',
  id: 'id',
}

export const postLanguageOgLocales: Record<PostLanguageCode, string> = {
  ru: 'ru_RU',
  en: 'en_US',
  es: 'es_ES',
  pt: 'pt_PT',
  de: 'de_DE',
  fr: 'fr_FR',
  tr: 'tr_TR',
  id: 'id_ID',
}

const postLanguageAliases = new Map<string, PostLanguageCode>([
  ['en-us', 'en'],
  ['en-gb', 'en'],
  ['en-au', 'en'],
  ['en-ca', 'en'],
  ['es-es', 'es'],
  ['es-mx', 'es'],
  ['es-ar', 'es'],
  ['pt-br', 'pt'],
  ['pt-pt', 'pt'],
  ['de-de', 'de'],
  ['de-at', 'de'],
  ['de-ch', 'de'],
  ['fr-fr', 'fr'],
  ['fr-ca', 'fr'],
  ['fr-be', 'fr'],
  ['tr-tr', 'tr'],
  ['id-id', 'id'],
  ['ru-ru', 'ru'],
])

export const isPostLanguageCode = (value: string | undefined | null): value is PostLanguageCode =>
  postLanguageCodes.includes(value as PostLanguageCode)

export const normalizePostLanguage = (value: string | undefined | null): PostLanguageCode =>
  isPostLanguageCode(value) ? value : originalPostLanguage

export const normalizeInterfaceLanguage = (
  value: string | undefined | null
): PostLanguageCode | null => {
  const normalized = String(value || '').trim().toLowerCase()
  if (!normalized) return null
  if (isPostLanguageCode(normalized)) return normalized
  const alias = postLanguageAliases.get(normalized)
  if (alias) return alias
  const baseLanguage = normalized.split('-')[0]
  return isPostLanguageCode(baseLanguage) ? baseLanguage : null
}

export const languageFromPathname = (pathname: string): PostLanguageCode | null => {
  const firstSegment = pathname.split('/').filter(Boolean)[0] || ''
  return normalizeInterfaceLanguage(firstSegment)
}

export const languageFromAcceptLanguage = (
  header: string | null | undefined
): PostLanguageCode | null => {
  if (!header) return null
  const candidates = header
    .split(',')
    .map((part) => {
      const [language, ...params] = part.trim().split(';')
      const qParam = params.find((param) => param.trim().startsWith('q='))
      const q = qParam ? Number(qParam.trim().slice(2)) : 1
      return { language, q: Number.isFinite(q) ? q : 0 }
    })
    .sort((left, right) => right.q - left.q)

  for (const candidate of candidates) {
    const language = normalizeInterfaceLanguage(candidate.language)
    if (language) return language
  }

  return null
}

export const buildLocalizedPostPath = (canonicalId: string, language: PostLanguageCode): string =>
  language === originalPostLanguage ? `/b/post/${canonicalId}` : `/${language}/b/post/${canonicalId}`
