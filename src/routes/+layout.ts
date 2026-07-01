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
  const savedLocale = browser ? get(userSettings)?.language : null
  const browserLocale = browser ? navigator?.language : null
  const normalizedLocale =
    routeLocale ??
    normalizeInterfaceLanguage(savedLocale) ??
    normalizeInterfaceLanguage(browserLocale) ??
    normalizeInterfaceLanguage(data?.language) ??
    originalPostLanguage

  await loadTranslations(normalizedLocale)

  if (browser && (!savedLocale || routeLocale || savedLocale !== normalizedLocale)) {
    userSettings.update((settings) => ({
      ...settings,
      language: normalizedLocale,
    }))
  }

  return
}
