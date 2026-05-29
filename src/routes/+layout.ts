import { browser } from '$app/environment'
import { env } from '$env/dynamic/public'
import { userSettings } from '$lib/settings.js'
import { aliases, loadTranslations } from '$lib/translations.js'
import { get } from 'svelte/store'

export const ssr = (env.PUBLIC_SSR_ENABLED?.toLowerCase() ?? 'true') !== 'false'

export const load = async ({}) => {
  if (browser) {
    const initLocale =
      get(userSettings)?.language ?? navigator?.language ?? 'en'

    await loadTranslations(aliases.get(initLocale) ?? initLocale)
  }

  return
}
