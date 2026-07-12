<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import {
    buildFavoritesFeedUrl,
    buildHomeFeedUrl,
    buildMyFeedUrl,
  } from '$lib/api/backend'
  import FeedPostsList from '$lib/components/feeds/FeedPostsList.svelte'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import { feedSettingsHydrated, userSettings } from '$lib/settings'
  import { locale, t } from '$lib/translations'
  import { normalizeInterfaceLanguage, originalPostLanguage } from '$lib/postLanguages'
  import { onDestroy, onMount } from 'svelte'
  import type { ComponentType } from 'svelte'
  import type { BackendPost } from '$lib/api/backend'

  export let data

  type LazyModule = { default: ComponentType }

  const pageSize = 10
  const scrollThreshold = 400

  let feedType = data.feedType ?? 'hot'
  let posts = data.posts ?? []
  let offset = posts.length
  let hasMore = posts.length === pageSize
  let loadingMore = false
  let feedParam: string | null = null
  let readParam: string | null = null
  let readOnly = false
  let lastPostsRef = data.posts
  let lastFeedType = feedType
  let lastFeedKey: string | null = null
  let lastMyFeedKey = ''
  let scrollRaf: number | null = null
  let myFeedSectionModulePromise: Promise<LazyModule> | null = null
  let showFeedKeyboardShortcutsHint = false
  let reusedInitialServerFeed = false

  const buildPageUrl = (currentOffset: number, limit = pageSize) => {
    let baseUrl = buildHomeFeedUrl({
      hideRead: effectiveHideRead,
      onlyRead: readOnly,
      card: true,
      language: currentLanguage,
    })
    if (feedType === 'favorites') {
      baseUrl = buildFavoritesFeedUrl({ language: currentLanguage })
    } else if (feedType === 'mine') {
      baseUrl = $siteUser
        ? buildMyFeedUrl(
            undefined,
            undefined,
            undefined,
            undefined,
            hideNegativeMyFeed,
            effectiveHideRead,
            readOnly,
            currentLanguage
          )
        : buildMyFeedUrl(
            selectedMyFeedAuthors,
            [],
            selectedMyFeedComuns,
            selectedMyFeedComunCategories,
            hideNegativeMyFeed,
            effectiveHideRead,
            readOnly,
            currentLanguage
          )
    }
    const url = new URL(baseUrl, $page.url.origin)
    url.searchParams.set('limit', String(limit))
    url.searchParams.set('offset', String(currentOffset))
    return url.toString()
  }

  const authorKey = (backendPost: { author?: { username?: string } }) =>
    (backendPost.author?.username ?? '').trim().toLowerCase()

  const isAuthorVisible = (backendPost: { author?: { username?: string } }) => {
    const key = authorKey(backendPost)
    if (!key) return true
    return !hiddenAuthorKeys.has(key)
  }

  const loadMore = async (limit = pageSize) => {
    if (!browser || loadingMore || !hasMore) return
    if (feedType === 'mine' && !canLoadMyFeed) return
    if (feedType === 'favorites' && !$siteUser) return
    if (readOnly && !$siteUser) return
    loadingMore = true
    try {
      const token = $siteToken
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined
      const response = await fetch(buildPageUrl(offset, limit), {
        headers,
      })
      if (!response.ok) {
        hasMore = false
        return
      }
      const payload = await response.json()
      const nextPosts = payload.posts ?? []
      if (nextPosts.length) {
        posts = [...posts, ...nextPosts]
        offset += nextPosts.length
      }
      if (nextPosts.length < limit) {
        hasMore = false
      }
      return nextPosts.length
    } catch (error) {
      console.error('Failed to load more posts:', error)
    } finally {
      loadingMore = false
    }
  }

  const maybeLoadMore = () => {
    if (!browser || loadingMore || !hasMore) return
    const viewportBottom = window.scrollY + window.innerHeight
    const pageHeight = document.documentElement.scrollHeight
    if (pageHeight - viewportBottom <= scrollThreshold) {
      void loadMore()
    }
  }

  const onScroll = () => {
    if (scrollRaf !== null) return
    scrollRaf = window.requestAnimationFrame(() => {
      scrollRaf = null
      maybeLoadMore()
    })
  }

  const openReadPosts = () => {
    const url = new URL($page.url)
    url.searchParams.set('read', '1')
    url.searchParams.set('feed', feedType)
    goto(`${url.pathname}?${url.searchParams.toString()}`)
  }

  const closeReadPosts = () => {
    const url = new URL($page.url)
    url.searchParams.delete('read')
    url.searchParams.set('feed', feedType)
    goto(`${url.pathname}?${url.searchParams.toString()}`)
  }

  onMount(() => {
    if (!browser) return
    maybeLoadMore()
    window.addEventListener('scroll', onScroll, { passive: true })
  })

  onDestroy(() => {
    if (!browser) return
    window.removeEventListener('scroll', onScroll)
    if (scrollRaf !== null) {
      window.cancelAnimationFrame(scrollRaf)
      scrollRaf = null
    }
  })

  $: if (data?.posts) {
    if (
      data.posts !== lastPostsRef &&
      data.feedType === feedType &&
      data.feedType !== 'mine' &&
      data.feedType !== 'favorites'
    ) {
      lastPostsRef = data.posts
      posts = data.posts ?? []
      offset = posts.length
      hasMore = posts.length === pageSize
      loadingMore = false
    }
  }

  $: feedParam = $page.url.searchParams.get('feed')
  $: readParam = $page.url.searchParams.get('read')
  $: readOnly = readParam === '1' || readParam === 'true' || readParam === 'yes'
  $: serverSelectedAuthenticatedFeed =
    Boolean(
      data?.authenticated &&
        data?.serverLoadedFeed &&
        !feedParam &&
        data?.feedType &&
        data.feedType !== 'hot'
    )
  $: waitForServerFeedHydration =
    browser && serverSelectedAuthenticatedFeed && !$feedSettingsHydrated

  $: selectedMyFeedComuns = $userSettings.myFeedComuns ?? []
  $: selectedMyFeedAuthors = $userSettings.myFeedAuthors ?? []
  $: selectedMyFeedComunCategories = $userSettings.myFeedComunCategories ?? {}
  $: myFeedHasBaseSettings = selectedMyFeedComuns.length > 0 || selectedMyFeedAuthors.length > 0
  $: hiddenAuthorKeys = new Set(
    ($userSettings.hiddenAuthors ?? []).map((value) => value.toLowerCase())
  )
  $: canLoadMyFeed =
    feedType === 'mine' && $siteUser && $feedSettingsHydrated && myFeedHasBaseSettings
  $: hideNegativeMyFeed = $userSettings.myFeedHideNegative ?? true
  $: hideReadPosts = ($userSettings.hideReadPosts ?? false) && !!$siteUser
  $: effectiveHideRead = hideReadPosts && !readOnly
  $: visiblePosts = posts.filter(isAuthorVisible) as BackendPost[]
  $: showFeedKeyboardShortcutsHint = feedType === 'hot' || feedType === 'mine'

  $: if (feedType === 'mine' && browser && !myFeedSectionModulePromise) {
    myFeedSectionModulePromise = import('$lib/components/feeds/MyFeedSection.svelte')
  }

  $: if (data?.feedType && data.feedType !== lastFeedType && feedParam) {
    lastFeedType = data.feedType
    feedType = data.feedType ?? 'hot'
    if (feedType === 'mine' || feedType === 'favorites') {
      posts = []
      offset = 0
      hasMore = false
      loadingMore = false
      lastMyFeedKey = ''
    } else {
      posts = data.posts ?? []
      offset = posts.length
      hasMore = posts.length === pageSize
      loadingMore = false
    }
  }

  $: if (!feedParam && !waitForServerFeedHydration) {
    const preferredFeed = $userSettings.homeFeed ?? 'hot'
    if (preferredFeed !== feedType) {
      feedType = preferredFeed
      lastFeedType = preferredFeed
      if (feedType === 'mine' || feedType === 'favorites') {
        posts = []
        offset = 0
        hasMore = false
        loadingMore = false
        lastMyFeedKey = ''
      } else {
        posts = []
        offset = 0
        hasMore = true
        loadingMore = false
        if (browser) {
          void loadMore()
        }
      }
    }
  }

  $: if (feedType !== 'mine' && feedType !== 'favorites') {
    const feedKey = [
      feedType,
      readOnly ? 'only-read' : effectiveHideRead ? 'hide-read' : 'all',
      hideNegativeMyFeed ? 'hide-neg' : 'show-neg',
      currentLanguage,
    ].join('|')
    if (lastFeedKey === null) {
      lastFeedKey = feedKey
      if ((effectiveHideRead || readOnly) && browser) {
        posts = []
        offset = 0
        hasMore = true
        loadingMore = false
        void loadMore()
      }
    } else if (feedKey !== lastFeedKey) {
      lastFeedKey = feedKey
      posts = []
      offset = 0
      hasMore = true
      loadingMore = false
      if (browser) {
        void loadMore()
      }
    }
  }

  $: if (feedType === 'mine') {
    if (waitForServerFeedHydration) {
      // Keep the SSR-selected feed visible until saved feed settings hydrate.
    } else {
      const authKey = $siteUser ? 'auth' : 'anon'
      const hydrationKey = $siteUser
        ? ($feedSettingsHydrated ? 'settings-ready' : 'settings-loading')
        : 'no-settings'
      const key = `${authKey}:${hydrationKey}:${currentLanguage}:${selectedMyFeedComuns.join(',')}:${selectedMyFeedAuthors.join(',')}:${JSON.stringify(selectedMyFeedComunCategories)}:${hideNegativeMyFeed ? 'no-negative' : 'all'}:${readOnly ? 'only-read' : effectiveHideRead ? 'hide-read' : 'all-read'}`
      if (key !== lastMyFeedKey) {
        lastMyFeedKey = key
        const canReuseServerInitialFeed =
          !reusedInitialServerFeed &&
          serverSelectedAuthenticatedFeed &&
          data?.feedType === 'mine' &&
          data?.serverLoadedFeed
        if (canReuseServerInitialFeed) {
          reusedInitialServerFeed = true
          offset = posts.length
          hasMore = posts.length === pageSize
          loadingMore = false
        } else {
          posts = []
          offset = 0
          hasMore = false
          loadingMore = false
        }
        if (canLoadMyFeed && !canReuseServerInitialFeed) {
          hasMore = true
          void loadMore()
        }
      }
    }
  }

  $: if (feedType === 'favorites') {
    if (waitForServerFeedHydration) {
      // Keep the SSR-selected feed visible until saved feed settings hydrate.
    } else {
      const authKey = $siteUser ? 'auth' : 'anon'
      const key = `favorites:${authKey}:${currentLanguage}`
      if (key !== lastMyFeedKey) {
        lastMyFeedKey = key
        const canReuseServerInitialFeed =
          !reusedInitialServerFeed &&
          serverSelectedAuthenticatedFeed &&
          data?.feedType === 'favorites' &&
          data?.serverLoadedFeed
        if (canReuseServerInitialFeed) {
          reusedInitialServerFeed = true
          offset = posts.length
          hasMore = posts.length === pageSize
          loadingMore = false
        } else {
          posts = []
          offset = 0
          hasMore = !!$siteUser
          loadingMore = false
        }
        if ($siteUser && browser && !canReuseServerInitialFeed) {
          void loadMore()
        }
      }
    }
  }

  $: siteBaseUrl = (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '')
  $: canonicalUrl = `${siteBaseUrl}/`
  $: currentLanguage = normalizeInterfaceLanguage($locale) || originalPostLanguage
  $: homeTitle =
    currentLanguage === originalPostLanguage
      ? env.PUBLIC_OG_TITLE || $t('site.meta.homeTitle')
      : $t('site.meta.homeTitle')
  $: homeDescription =
    currentLanguage === originalPostLanguage
      ? env.PUBLIC_SITE_DESCRIPTION || env.PUBLIC_OG_DESCRIPTION || $t('site.meta.homeDescription')
      : $t('site.meta.homeDescription')
</script>

<div class="flex max-w-full min-w-0 w-full flex-col gap-2">
  {#if feedType === 'favorites'}
    <header class="relative flex flex-col gap-2">
      <h1 class="text-2xl font-semibold text-slate-900 dark:text-zinc-100">
        Избранное
      </h1>
    </header>
  {/if}

  {#if $siteUser && readOnly && feedType !== 'favorites'}
    <div class="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900">
      <div class="text-sm text-slate-600 dark:text-zinc-300">
        {$t('site.feed.readOnlyNotice')}
      </div>
      <button
        type="button"
        class="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
        on:click={closeReadPosts}
      >
        {$t('site.feed.returnToFeed')}
      </button>
    </div>
  {:else if $siteUser && feedType !== 'favorites' && effectiveHideRead}
    <div class="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900">
      <div class="text-sm text-slate-600 dark:text-zinc-300">
        {$t('site.feed.readPostsHidden')}
      </div>
      <button
        type="button"
        class="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
        on:click={openReadPosts}
      >
        {$t('site.feed.showReadPosts')}
      </button>
    </div>
  {/if}

  {#if feedType === 'mine'}
    {#if myFeedSectionModulePromise}
      {#await myFeedSectionModulePromise then module}
        <svelte:component
          this={module.default}
          {posts}
          {loadingMore}
          showKeyboardShortcutsHint={showFeedKeyboardShortcutsHint}
        />
      {/await}
    {/if}
  {:else if feedType === 'favorites' && !$siteUser}
    <div class="text-base text-slate-500">
      После регистрации вы сможете добавлять посты в избранное и видеть их в отдельной ленте.
    </div>
  {:else if visiblePosts.length}
    <FeedPostsList
      posts={visiblePosts}
      {loadingMore}
      showKeyboardShortcutsHint={showFeedKeyboardShortcutsHint}
    />
  {:else}
    <div class="text-base text-slate-500">Пока нет публикаций.</div>
  {/if}
</div>

<svelte:head>
  <title>{homeTitle}</title>
  <meta name="description" content={homeDescription} />
  <meta property="og:title" content={homeTitle} />
  <meta property="og:description" content={homeDescription} />
  <meta property="og:image" content={env.PUBLIC_OG_IMAGE} />
  <meta property="og:url" content={env.PUBLIC_OG_URL} />
  <meta property="og:type" content="website" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={env.PUBLIC_TWITTER_TITLE} />
  <meta name="twitter:description" content={env.PUBLIC_TWITTER_DESCRIPTION} />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
