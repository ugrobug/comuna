import {
  postLanguageCodes,
  type PostLanguageCode,
} from '$lib/postLanguages'

export const interfaceLanguageFlags: Record<PostLanguageCode, string> = {
  ru: '🇷🇺',
  en: '🇬🇧',
  es: '🇪🇸',
  pt: '🇵🇹',
  de: '🇩🇪',
  fr: '🇫🇷',
  tr: '🇹🇷',
  id: '🇮🇩',
}

export const interfaceLanguageOptions = postLanguageCodes.map((code) => ({
  code,
  flag: interfaceLanguageFlags[code],
}))
