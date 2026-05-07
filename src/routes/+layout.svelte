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
  import SiteCard from '$lib/components/lemmy/SiteCard.svelte'
  import { site } from '$lib/lemmy.js'
  import ExpandableImage from '$lib/components/ui/ExpandableImage.svelte'
  import { LINKED_INSTANCE_URL } from '$lib/instance'
  import { locale } from '$lib/translations'
  import { getDefaultColors } from '$lib/ui/presets'
  import { env } from '$env/dynamic/public'
  import YandexMetrika from '$lib/components/YandexMetrika.svelte'
  import GoogleAnalytics from '$lib/components/GoogleAnalytics.svelte'

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
    $page.url.pathname === '/lp' || $page.url.pathname.startsWith('/lp/')
  // Получаем текущий URL для канонической ссылки
  $: siteBaseUrl = (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '')
  $: canonicalUrl = (() => {
    if ($page.url.pathname === '/' || $page.url.pathname === '') {
      return siteBaseUrl
    }
    const path = $page.url.pathname
    const cleanPath = path.replace(/\/+$/, '')
    return `${siteBaseUrl}${cleanPath}`
  })()
  $: defaultTitle = env.PUBLIC_SITE_TITLE || 'Comuna'
  $: defaultDescription = env.PUBLIC_SITE_DESCRIPTION || 'Публикуем лучшие посты из Telegram-каналов.'
  $: siteTitle = $site?.site_view?.site?.name || defaultTitle
  $: siteDescription = $site?.site_view?.site?.description || defaultDescription
  $: isBackendPostRoute = $page.url.pathname.startsWith('/b/post/')
  $: keyboardShortcutsHintEnabled = new Set([
    '/',
    '/about',
    '/[username]',
    '/tags/[tag]',
    '/c/[name]',
    '/post/[slug]',
    '/profile/voted/[type]',
  ]).has($page.route.id ?? '')
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
        inLanguage: 'ru-RU',
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
      userSettings.subscribe((settings) => {
        console.log('Current font settings:', settings.font);
        console.log('Adding font class:', settings.font === 'roboto' ? 'font-roboto' : 'font-sans');
      })
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
    {/if}
  <link rel="canonical" href={canonicalUrl} />
  
  <!-- Добавляем мета-тег noindex для страниц inbox -->
  {#if $page.url.pathname.startsWith('/inbox')}
    <meta name="robots" content="noindex, nofollow" />
  {/if}
  
  <!-- Добавляем специальные мета-теги для HTTP версии -->
  {#if !$page.url.protocol.includes('https')}
    <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
  {/if}
  
  <!-- Добавляем alternate для языковых версий, если они есть -->
  <link rel="alternate" hreflang="ru" href={canonicalUrl} />
  <link rel="alternate" hreflang="x-default" href={canonicalUrl} />

  {@html siteSchemaTag}
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
  fullBleed={isLandingRoute}
>
  <Moderation />
  <ToastContainer />
  <ExpandableImage />
  <ModalContainer />

  <svelte:fragment slot="sidebar" let:style={s} let:class={c}>
    {#if !isLandingRoute}
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
    class="{isLandingRoute
      ? 'min-w-0 w-full flex flex-col h-full relative xl:pt-0 pt-20'
      : 'p-4 sm:p-6 min-w-0 w-full flex flex-col h-full relative xl:pt-0 pt-20'} {c}"
    style={s}
    id="main"
  >
    <slot />
  </main>
  <Navbar slot="navbar" let:style={s} let:class={c} class={c} style={s} />
  
  <svelte:fragment slot="suffix" let:class={c} let:style={s}>
    {#if !isLandingRoute && !$page.data.hideSidebar}
      <div 
        class={c}
        style={s}
      >
        <div class="flex flex-col gap-4 h-[calc(100vh-4rem)] sticky top-16 p-4">
          <!-- Прокручиваемый контент сайдбара -->
          <div class="flex flex-col gap-4 flex-1 min-h-0 overflow-auto hover:scrollbar scrollbar-hidden">
            <!-- CommunityCard или SiteCard -->
            {#if $page.data.slots?.sidebar?.component}
              <div class="flex-shrink-0">
                <svelte:component
                  this={$page.data.slots.sidebar.component}
                  {...$page.data.slots.sidebar.props}
                />
              </div>
            {/if}
            
            {#if !$page.data.slots?.sidebar?.component}
              {#await import('$lib/components/ui/sidebar/DefaultSidebarWidgets.svelte') then { default: DefaultSidebarWidgets }}
                <DefaultSidebarWidgets {keyboardShortcutsHintEnabled} />
              {/await}
            {/if}
          </div>
        </div>
      </div>
    {/if}
  </svelte:fragment>
</Shell>

<style>
  /* Базовые стили для скрытия полосы прокрутки */
  .scrollbar-hidden::-webkit-scrollbar {
    width: 0.25rem;
    background: transparent;
  }
  
  .scrollbar-hidden::-webkit-scrollbar-thumb {
    background: transparent;
  }

  /* Показываем полосу прокрутки при наведении */
  .hover\:scrollbar:hover::-webkit-scrollbar-thumb {
    background: rgb(203 213 225 / 0.3); /* slate-200 с прозрачностью */
    border-radius: 0.25rem;
  }

  .dark .hover\:scrollbar:hover::-webkit-scrollbar-thumb {
    background: rgb(39 39 42 / 0.3); /* zinc-800 с прозрачностью */
  }

  .hover\:scrollbar:hover::-webkit-scrollbar-thumb:hover {
    background: rgb(203 213 225 / 0.5);
  }

  .dark .hover\:scrollbar:hover::-webkit-scrollbar-thumb:hover {
    background: rgb(39 39 42 / 0.5);
  }
</style>
