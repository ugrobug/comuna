import { browser } from '$app/environment'
import { env } from '$env/dynamic/public'
import { userSettings } from '$lib/settings.js'
import {
  languageFromPathname,
  normalizeInterfaceLanguage,
  originalPostLanguage,
} from '$lib/postLanguages.js'
import { loadTranslations } from '$lib/translations.js'
import { get } from 'svelte/store'

export const ssr = (env.PUBLIC_SSR_ENABLED?.toLowerCase() ?? 'true') !== 'false'

export const load = async ({ url, data }) => {
  const routeLocale = languageFromPathname(url.pathname)
  const settings = browser ? get(userSettings) : null
  const savedLocale =
    settings?.languageManuallySelected ? normalizeInterfaceLanguage(settings.language) : null
  const browserLocale = browser
    ? (navigator?.languages
        ?.map((language) => normalizeInterfaceLanguage(language))
        .find(Boolean) ??
      normalizeInterfaceLanguage(navigator?.language))
    : null
  const normalizedLocale =
    savedLocale ??
    browserLocale ??
    normalizeInterfaceLanguage(data?.language) ??
    routeLocale ??
    originalPostLanguage

  await loadTranslations(normalizedLocale)

  return
}
