import {
  languageFromAcceptLanguage,
  languageFromPathname,
  originalPostLanguage,
} from '$lib/postLanguages.js'
import { loadTranslations } from '$lib/translations.js'

export const load = async ({ url, request }) => {
  const language =
    languageFromPathname(url.pathname) ||
    languageFromAcceptLanguage(request.headers.get('Accept-Language')) ||
    originalPostLanguage

  await loadTranslations(language)
  return { language }
}
