<script lang="ts">
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { userSettings } from '$lib/settings'
  import {
    interfaceLanguageFlags,
    interfaceLanguageOptions,
  } from '$lib/interfaceLanguages'
  import { loadTranslations, locale, t } from '$lib/translations'
  import {
    isPostLanguageCode,
    originalPostLanguage,
    type PostLanguageCode,
  } from '$lib/postLanguages'
  import { Check, Icon } from 'svelte-hero-icons'

  const languages = interfaceLanguageOptions

  let switching = false

  $: currentLanguage = isPostLanguageCode($locale)
    ? $locale
    : originalPostLanguage

  const stripLanguagePrefix = (pathname: string) => {
    const segments = pathname.split('/').filter(Boolean)
    if (isPostLanguageCode(segments[0])) {
      segments.shift()
    }
    return `/${segments.join('/')}`
  }

  const supportsLocalizedPath = (pathname: string) =>
    pathname === '/b/post' || pathname.startsWith('/b/post/')

  const getLanguageHref = (language: PostLanguageCode) => {
    const basePath = stripLanguagePrefix($page.url.pathname)
    const nextPath =
      language === originalPostLanguage || !supportsLocalizedPath(basePath)
        ? basePath
        : `/${language}${basePath}`

    return `${nextPath}${$page.url.search}${$page.url.hash}`
  }

  async function selectLanguage(language: PostLanguageCode) {
    if (switching || language === currentLanguage) return

    switching = true
    try {
      await loadTranslations(language)
      userSettings.update((settings) => ({
        ...settings,
        language,
      }))

      const target = getLanguageHref(language)
      const current = `${$page.url.pathname}${$page.url.search}${$page.url.hash}`
      if (target !== current) {
        await goto(target, {
          keepFocus: true,
          noScroll: true,
        })
      }
    } finally {
      switching = false
    }
  }
</script>

<div class="language-switcher relative h-8 md:h-10">
  <button
    type="button"
    class="language-trigger h-8 w-8 md:h-10 md:w-10 rounded-full border border-slate-200 dark:border-zinc-700 bg-white/60 dark:bg-zinc-950/50 flex items-center justify-center text-lg leading-none transition-colors hover:bg-slate-100 dark:hover:bg-zinc-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
    title={$t('site.language.select')}
    aria-label={$t('site.language.select')}
    aria-haspopup="menu"
  >
    <span aria-hidden="true">{interfaceLanguageFlags[currentLanguage]}</span>
  </button>

  <div
    class="language-menu pointer-events-none absolute right-0 top-full z-[150] w-56 pt-2 opacity-0 transition duration-150"
  >
    <div
      class="rounded-xl border border-slate-200/80 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/95 p-2 shadow-lg backdrop-blur-xl"
      role="menu"
      aria-label={$t('site.language.select')}
    >
      {#each languages as language (language.code)}
        <button
          type="button"
          class="flex min-h-[38px] w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:cursor-default disabled:opacity-80 {language.code === currentLanguage
            ? 'bg-slate-100 dark:bg-zinc-800'
            : ''}"
          role="menuitemradio"
          aria-checked={language.code === currentLanguage}
          disabled={switching}
          on:click={() => selectLanguage(language.code)}
        >
          <span class="text-lg leading-none" aria-hidden="true">{language.flag}</span>
          <span class="flex-1 text-slate-800 dark:text-zinc-100">
            {$t(`site.language.names.${language.code}`)}
          </span>
          {#if language.code === currentLanguage}
            <span class="text-primary-600 dark:text-primary-400" title={$t('site.language.current')}>
              <Icon src={Check} size="16" mini />
            </span>
          {/if}
        </button>
      {/each}
    </div>
  </div>
</div>

<style>
  .language-switcher:hover .language-menu,
  .language-switcher:focus-within .language-menu {
    opacity: 1;
    pointer-events: auto;
  }
</style>
