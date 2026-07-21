<script lang="ts">
  import Navbar from '$lib/components/ui/navbar/Navbar.svelte'
  import '../style/app.css'
  import { navigating, page } from '$app/stores'
  import nProgress from 'nprogress'
  import 'nprogress/nprogress.css'
  import Moderation from '$lib/components/lemmy/moderation/Moderation.svelte'
  import {
    colorScheme,
    inDarkColorScheme,
    rgbToHex,
    themeVars,
  } from '$lib/ui/colors.js'
  import { userSettings } from '$lib/settings.js'
  import {
    Button,
    ModalContainer,
    Spinner,
    toast,
    ToastContainer,
  } from 'mono-svelte'
  import { onMount } from 'svelte'
  import { browser } from '$app/environment'
  import { Forward, Icon } from 'svelte-hero-icons'
  import { routes } from '$lib/util.js'
  import Shell from '$lib/components/ui/layout/Shell.svelte'
  import { site } from '$lib/lemmy.js'
  import ExpandableImage from '$lib/components/ui/ExpandableImage.svelte'
  import { LINKED_INSTANCE_URL } from '$lib/instance'
  import { locale, t } from '$lib/translations'
  import { brandNameForLanguage } from '$lib/brand'
  import { normalizeInterfaceLanguage, postLanguageLocales, postLanguageOgLocales } from '$lib/postLanguages'
  import { getDefaultColors } from '$lib/ui/presets'
  import { env } from '$env/dynamic/public'
  import YandexMetrika from '$lib/components/YandexMetrika.svelte'
  import GoogleAnalytics from '$lib/components/GoogleAnalytics.svelte'
  import CookieNotice from '$lib/components/CookieNotice.svelte'
  import MobileBottomNavigation from '$lib/components/ui/navbar/MobileBottomNavigation.svelte'

  nProgress.configure({
    minimum: 0.4,
    trickleSpeed: 200,
    easing: 'ease-out',
    speed: 300,
    showSpinner: false,
  })

  onMount(() => {
    if (!('serviceWorker' in navigator)) return
    navigator.serviceWorker.getRegistrations().then((regs) => {
      regs.forEach((reg) => reg.unregister())
    })
  })

  let barTimeout: any = 0

  $: {
    if (browser) {
      if ($navigating) {
        document.body.classList.toggle('wait', true)
        barTimeout = setTimeout(() => nProgress.start(), 100)
      }
      if (!$navigating) {
        document.body.classList.toggle('wait', false)
        clearTimeout(barTimeout)
        nProgress.done()
      }
    }
  }

  $: isLandingRoute =
    $page.url.pathname === '/lp' ||
    $page.url.pathname.startsWith('/lp/') ||
    $page.url.pathname === '/l' ||
    $page.url.pathname.startsWith('/l/')
  $: isSpecialProjectRoute = $page.url.pathname.startsWith('/s/')
  $: isFullBleedRoute = isLandingRoute || isSpecialProjectRoute
  $: isMobileNavigationExcludedRoute =
    /^\/(?:account\/(?:new-post|edit-post)|create\/post|edit\/post|drafts|login|signup)(?:\/|$)/.test(
      $page.url.pathname
    )
  $: showMobileBottomNavigation = !isFullBleedRoute && !isMobileNavigationExcludedRoute
  // Получаем текущий URL для канонической ссылки
  $: siteBaseUrl = (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '')
  $: canonicalUrl = (() => {
    if ($page.url.pathname === '/') {
      return siteBaseUrl
    }
    const path = $page.url.pathname
    const cleanPath = path.replace(/\/+$/, '')
    return `${siteBaseUrl}${cleanPath}`
  })()
  $: currentLanguage = normalizeInterfaceLanguage($locale) || 'ru'
  $: shouldLoadAdsense = currentLanguage !== 'ru'
  $: defaultTitle = brandNameForLanguage(currentLanguage)
  $: defaultDescription = $t('site.meta.defaultDescription')
  $: siteTitle =
    currentLanguage === 'ru' ? $site?.site_view?.site?.name || defaultTitle : defaultTitle
  $: siteDescription =
    currentLanguage === 'ru'
      ? $site?.site_view?.site?.description || env.PUBLIC_SITE_DESCRIPTION || defaultDescription
      : defaultDescription
  $: isBackendPostRoute = /^\/(?:[a-z]{2}\/)?b\/post\//.test($page.url.pathname)
  $: isLocalizedStaticPageRoute =
    /^\/(?:[a-z]{2}\/)?(?:about|advertisement|apps|authors|rules)\/?$/.test(
      $page.url.pathname
    )
  $: isCommunityDetailRoute = /^\/(?:[a-z]{2}\/)?comuns\/[^/]+\/?$/.test(
    $page.url.pathname
  )
  $: hasRouteManagedSeo =
    isBackendPostRoute || isLocalizedStaticPageRoute || isCommunityDetailRoute
  const toJsonLd = (value: unknown) =>
    JSON.stringify(value)
      .replace(/</g, '\\u003c')
      .replace(/>/g, '\\u003e')
      .replace(/&/g, '\\u0026')

  const buildJsonLdTag = (json: string) =>
    json ? `<script type="application/ld+json">${json}</` + `script>` : ''

  $: siteSchemaJson = toJsonLd({
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Organization',
        '@id': `${siteBaseUrl}#organization`,
        name: siteTitle,
        url: siteBaseUrl,
        logo: {
          '@type': 'ImageObject',
          url: `${siteBaseUrl}/favicon_120x120.svg`,
        },
      },
      {
        '@type': 'WebSite',
        '@id': `${siteBaseUrl}#website`,
        url: siteBaseUrl,
        name: siteTitle,
        description: siteDescription,
        publisher: { '@id': `${siteBaseUrl}#organization` },
        inLanguage: postLanguageLocales[currentLanguage],
        potentialAction: {
          '@type': 'SearchAction',
          target: `${siteBaseUrl}/search?q={search_term_string}`,
          'query-input': 'required name=search_term_string',
        },
      },
    ],
  })
  $: siteSchemaTag = buildJsonLdTag(siteSchemaJson)

  onMount(() => {
    if (browser) {
      if (window.location.hash == 'main') {
        history.replaceState(
          null,
          '',
          window.location.toString().replace('#main', '')
        )
      }
      document.body.querySelector('.loader')?.classList.add('hidden')
      document.body.setAttribute('style', themeVars)
    }
  })
</script>

<GoogleAnalytics />
<YandexMetrika />

<svelte:head>

  <title>{siteTitle}</title>
    <meta
      name="theme-color"
      content={rgbToHex(
        inDarkColorScheme()
          ? getDefaultColors().zinc[925]
          : getDefaultColors().slate[25]
      )}
    />
    <!-- Telegram uses a short HTML prefix for link previews; avoid generic description on post pages. -->
    {#if !isBackendPostRoute}
      <meta name="description" content={siteDescription} />
      <meta property="og:site_name" content={siteTitle} />
      <meta property="og:locale" content={postLanguageOgLocales[currentLanguage]} />
    {/if}
  {#if !hasRouteManagedSeo}
    <link rel="canonical" href={canonicalUrl} />
  {/if}
  
  <!-- Добавляем мета-тег noindex для страниц inbox -->
  {#if $page.url.pathname.startsWith('/inbox')}
    <meta name="robots" content="noindex, nofollow" />
  {/if}
  
  <!-- Добавляем специальные мета-теги для HTTP версии -->
  {#if !$page.url.protocol.includes('https')}
    <meta http-equiv="content-security-policy" content="upgrade-insecure-requests">
  {/if}
  
  {#if !hasRouteManagedSeo}
    <link rel="alternate" hreflang="ru" href={canonicalUrl} />
    <link rel="alternate" hreflang="x-default" href={canonicalUrl} />
  {/if}

  {@html siteSchemaTag}
  {#if shouldLoadAdsense}
    <script
      async
      src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1110344676156197"
      crossorigin="anonymous"
    ></script>
  {/if}
</svelte:head>

<Button
  class="fixed -top-16 focus:top-0 left-0 m-4 z-[300] transition-all"
  href="#main"
>
  <Icon src={Forward} mini size="16" slot="prefix" />
  Skip Navigation
</Button>
<Shell
  dir={$locale == 'he' && $userSettings.useRtl ? 'rtl' : 'ltr'}
  class="min-h-screen "
  route={$page.route}
  fullBleed={isFullBleedRoute}
>
  <Moderation />
  <ToastContainer />
  <ExpandableImage />
  <ModalContainer />
  <CookieNotice />

  <svelte:fragment slot="sidebar" let:style={s} let:class={c}>
    {#if !isFullBleedRoute}
      {#await import('$lib/components/ui/sidebar/Sidebar.svelte') then { default: Sidebar }}
        <Sidebar
          route={$page.route.id ?? ''}
          class="xl:pt-0 pt-20 {c}"
          style={s}
        />
      {/await}
    {/if}
  </svelte:fragment>
  <main
    slot="main"
    let:style={s}
    let:class={c}
    class="{isFullBleedRoute
      ? 'min-w-0 w-full flex flex-col h-full relative xl:pt-0 pt-20'
      : 'p-4 sm:p-6 min-w-0 w-full flex flex-col h-full relative xl:pt-0 pt-20'} {showMobileBottomNavigation ? 'mobile-bottom-nav-space' : ''} {c}"
    style={s}
    id="main"
  >
    <slot />
  </main>
  <Navbar slot="navbar" let:style={s} let:class={c} class={c} style={s} />
</Shell>

{#if showMobileBottomNavigation}
  <MobileBottomNavigation />
{/if}

<style>
  :global(.mobile-bottom-nav-space) {
    padding-bottom: calc(6rem + env(safe-area-inset-bottom, 0px)) !important;
  }

  @media (min-width: 768px) {
    :global(.mobile-bottom-nav-space) {
      padding-bottom: 1.5rem !important;
    }
  }
</style>
