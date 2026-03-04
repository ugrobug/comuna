<script lang="ts">
  // @ts-ignore Svelte component default export is generated during compilation.
  import Navbar from '$lib/components/ui/navbar/Navbar.svelte'
  import '../style/app.css'
  import { navigating, page } from '$app/stores'
  import nProgress from 'nprogress'
  import 'nprogress/nprogress.css'
  import Moderation from '$lib/components/lemmy/moderation/Moderation.svelte'
  import Sidebar from '$lib/components/ui/sidebar/Sidebar.svelte'
  import {
    colorScheme,
    inDarkColorScheme,
    rgbToHex,
    theme,
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
  import { onMount, type ComponentType } from 'svelte'
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

  nProgress.configure({
    minimum: 0.4,
    trickleSpeed: 200,
    easing: 'ease-out',
    speed: 300,
    showSpinner: false,
  })

  let GoogleAnalyticsComponent: ComponentType | null = null
  let YandexMetrikaComponent: ComponentType | null = null
  let PopularPostsComponent: ComponentType | null = null
  let RecentCommentsComponent: ComponentType | null = null
  let KeyboardShortcutsHintComponent: ComponentType | null = null

  const loadAnalytics = async () => {
    const [{ default: GoogleAnalytics }, { default: YandexMetrika }] =
      await Promise.all([
        import('$lib/components/GoogleAnalytics.svelte'),
        import('$lib/components/YandexMetrika.svelte'),
      ])
    GoogleAnalyticsComponent = GoogleAnalytics
    YandexMetrikaComponent = YandexMetrika
  }

  const loadSidebarWidgets = async () => {
    const [
      { default: PopularPosts },
      { default: RecentComments },
      { default: KeyboardShortcutsHint },
    ] = await Promise.all([
      import('$lib/components/ui/sidebar/PopularPosts.svelte'),
      import('$lib/components/ui/sidebar/RecentComments.svelte'),
      import('$lib/components/ui/sidebar/KeyboardShortcutsHint.svelte'),
    ])
    PopularPostsComponent = PopularPosts
    RecentCommentsComponent = RecentComments
    KeyboardShortcutsHintComponent = KeyboardShortcutsHint
  }

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

  // Исправляем условие проверки маршрута
  $: isPostFormRoute = $page.url.pathname.includes('/create/post') || $page.url.pathname.includes('/edit/post')

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
    '/rubrics/[slug]/posts',
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
    if (!browser) return

    if (window.location.hash == 'main') {
      history.replaceState(
        null,
        '',
        window.location.toString().replace('#main', '')
      )
    }
    document.body.querySelector('.loader')?.classList.add('hidden')
    const unsubscribeThemeVars = themeVars.subscribe((vars) => {
      document.body.setAttribute('style', vars)
    })
    const unsubscribeUserSettings = userSettings.subscribe((settings) => {
      console.log('Current font settings:', settings.font)
      console.log(
        'Adding font class:',
        settings.font === 'roboto' ? 'font-roboto' : 'font-sans'
      )
    })

    const sidebarWidgetsTimer = window.setTimeout(() => {
      loadSidebarWidgets().catch((error) => {
        console.error('Failed to load sidebar widgets', error)
      })
    }, 200)
    const analyticsTimer = window.setTimeout(() => {
      loadAnalytics().catch((error) => {
        console.error('Failed to load analytics components', error)
      })
    }, 1000)

    return () => {
      window.clearTimeout(sidebarWidgetsTimer)
      window.clearTimeout(analyticsTimer)
      unsubscribeThemeVars()
      unsubscribeUserSettings()
    }
  })
</script>

{#if GoogleAnalyticsComponent}
  <svelte:component this={GoogleAnalyticsComponent} />
{/if}
{#if YandexMetrikaComponent}
  <svelte:component this={YandexMetrikaComponent} />
{/if}

<svelte:head>

  <title>{siteTitle}</title>
    <meta
      name="theme-color"
      content={rgbToHex(
        $colorScheme && inDarkColorScheme()
          ? $theme.colors.zinc?.[925] ?? getDefaultColors().zinc[925]
          : $theme.colors.slate?.[25] ?? getDefaultColors().slate[25]
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
>
  <Moderation />
  <ToastContainer />
  <ExpandableImage />
  <ModalContainer />

  <Sidebar
    route={$page.route.id ?? ''}
    slot="sidebar"
    let:style={s}
    let:class={c}
    class="xl:pt-0 pt-20 {c}"
    style={s}
  />
  <main
    slot="main"
    let:style={s}
    let:class={c}
    class="p-4 sm:p-6 min-w-0 w-full flex flex-col h-full relative {c} xl:pt-0 pt-20"
    style={s}
    id="main"
  >
    <slot />
  </main>
  <Navbar slot="navbar" let:style={s} let:class={c} class={c} style={s} />
  
  <div 
    slot="suffix" 
    let:class={c} 
    let:style={s} 
    class="{c} {isPostFormRoute ? 'hidden' : ''}"
    style={s}
  >
    <div class="flex flex-col gap-4 h-[calc(100vh-4rem)] sticky top-16 p-4">
      <!-- Прокручиваемый контент сайдбара -->
      <div class="flex flex-col gap-4 flex-1 min-h-0 overflow-auto hover:scrollbar scrollbar-hidden">
        <!-- CommunityCard или SiteCard -->
        {#if $page.route.id?.startsWith('/c/') || $page.route.id?.startsWith('/post/')}
          <div class="flex-shrink-0">
            {#if $page.data.slots?.sidebar?.component}
              <svelte:component
                this={$page.data.slots.sidebar.component}
                {...$page.data.slots.sidebar.props}
              />
            {/if}
          </div>
        {/if}
        
        <!-- PopularPosts -->
        <div class="flex flex-col gap-4">
          {#if KeyboardShortcutsHintComponent}
            <svelte:component
              this={KeyboardShortcutsHintComponent}
              enabled={keyboardShortcutsHintEnabled}
            />
          {/if}
          {#if PopularPostsComponent}
            <svelte:component this={PopularPostsComponent} />
          {/if}
          {#if PopularPostsComponent || RecentCommentsComponent}
            <div class="h-px bg-slate-200 dark:bg-zinc-800"></div>
          {/if}
          {#if RecentCommentsComponent}
            <svelte:component this={RecentCommentsComponent} />
          {/if}
        </div>
      </div>
    </div>
  </div>
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
