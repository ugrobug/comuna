<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import {
    type BackendThematicFeed,
    buildFavoritesFeedUrl,
    buildHomeFeedUrl,
    buildMyFeedUrl,
    buildThematicFeedPostsUrl,
  } from '$lib/api/backend'
  import FeedPostsList from '$lib/components/feeds/FeedPostsList.svelte'
  import {
    buildMyFeedSettingsFromFolderPreset,
    hasMyFeedCustomizations,
  } from '$lib/feeds/myFeed'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import { feedSettingsHydrated, userSettings } from '$lib/settings'
  import { t } from '$lib/translations.js'
  import { onDestroy, onMount } from 'svelte'
  import { Cog6Tooth, Icon } from 'svelte-hero-icons'
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
  let hiddenReadCount = 0
  let thematicFeedSlug = data.thematicSlug ?? ''
  let thematicFeedMeta: BackendThematicFeed | null = data.thematicFeed ?? null
  let feedParam: string | null = null
  let readParam: string | null = null
  let readOnly = false
  let lastPostsRef = data.posts
  let lastFeedType = feedType
  let lastFeedKey: string | null = null
  let lastMyFeedKey = ''
  let scrollRaf: number | null = null
  let folderSettingsOpen = false
  let folderSettingsModalModulePromise: Promise<LazyModule> | null = null
  let myFeedSectionModulePromise: Promise<LazyModule> | null = null

  const canManageCurrentFolder = () => {
    if (!$siteUser || !thematicFeedMeta) return false
    if ($siteUser.is_staff) return true
    const currentUsername = ($siteUser.username ?? '').trim().toLowerCase()
    if (!currentUsername) return false
    return (thematicFeedMeta.moderators ?? []).some(
      (moderator) => (moderator?.username ?? '').trim().toLowerCase() === currentUsername
    )
  }

  const openCurrentFolderSettings = async () => {
    if (!thematicFeedSlug) return
    if (!$siteUser) {
      const next = encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)
      goto(`/account?next=${next}`)
      return
    }
    folderSettingsModalModulePromise ??= import(
      '$lib/components/feeds/ThematicFolderSettingsModal.svelte'
    )
    folderSettingsOpen = true
  }

  const closeCurrentFolderSettings = () => {
    folderSettingsOpen = false
  }

  const refreshCurrentFolderFeedAfterSettingsSave = async () => {
    if (!browser) return
    posts = []
    offset = 0
    hasMore = true
    loadingMore = false
    hiddenReadCount = 0
    await loadMore()
  }

  const applyThematicFeedToMyFeed = async () => {
    if (!thematicFeedMeta) return
    if (!$siteUser) {
      const next = encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)
      goto(`/account?next=${next}`)
      return
    }
    if (browser && hasMyFeedCustomizations($userSettings)) {
      const confirmed = window.confirm(
        'У вас уже настроена "Моя лента". Нажатие на кнопку заменит текущие настройки настройками папки. После этого вы сможете дополнительно настроить свою ленту. Продолжить?'
      )
      if (!confirmed) return
    }
    $userSettings = buildMyFeedSettingsFromFolderPreset($userSettings, thematicFeedMeta)
    goto('/?feed=mine')
  }

  const onThematicFeedUpdated = (folder: BackendThematicFeed) => {
    thematicFeedMeta = folder
  }

  const buildPageUrl = (currentOffset: number) => {
    let baseUrl = buildHomeFeedUrl({
      hideRead: effectiveHideRead,
      onlyRead: readOnly,
    })
    if (feedType === 'favorites') {
      baseUrl = buildFavoritesFeedUrl()
    } else if (feedType === 'thematic') {
      baseUrl = buildThematicFeedPostsUrl(thematicFeedSlug, {
        hideRead: effectiveHideRead,
        onlyRead: readOnly,
      })
    } else if (feedType === 'mine') {
      baseUrl = $siteUser
        ? buildMyFeedUrl(
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            effectiveHideRead,
            readOnly
          )
        : buildMyFeedUrl(
            selectedRubrics,
            selectedAuthors,
            selectedMyFeedTags,
            selectedMyFeedComuns,
            selectedMyFeedComunCategories,
            hideNegativeMyFeed,
            effectiveHideRead,
            readOnly
          )
    }
    const url = new URL(baseUrl)
    url.searchParams.set('limit', String(pageSize))
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

  const loadMore = async () => {
    if (!browser || loadingMore || !hasMore) return
    if (feedType === 'mine' && !canLoadMyFeed) return
    if (feedType === 'favorites' && !$siteUser) return
    if (feedType === 'thematic' && !thematicFeedSlug) return
    if (readOnly && !$siteUser) return
    loadingMore = true
    try {
      const token = $siteToken
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined
      const response = await fetch(buildPageUrl(offset), {
        headers,
      })
      if (!response.ok) {
        hasMore = false
        return
      }
      const payload = await response.json()
      if (payload?.thematic_feed && feedType === 'thematic') {
        thematicFeedMeta = payload.thematic_feed
      }
      if (typeof payload.hidden_read_count === 'number') {
        hiddenReadCount = payload.hidden_read_count
      }
      const nextPosts = payload.posts ?? []
      if (nextPosts.length) {
        posts = [...posts, ...nextPosts]
        offset += nextPosts.length
      }
      if (nextPosts.length < pageSize) {
        hasMore = false
      }
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
      if (data.feedType === 'thematic') {
        thematicFeedMeta = data.thematicFeed ?? null
      }
      offset = posts.length
      hasMore = posts.length === pageSize
      loadingMore = false
    }
  }

  $: feedParam = $page.url.searchParams.get('feed')
  $: thematicFeedSlug = ($page.url.searchParams.get('theme') ?? '').trim()
  $: readParam = $page.url.searchParams.get('read')
  $: readOnly = readParam === '1' || readParam === 'true' || readParam === 'yes'

  $: selectedRubrics = $userSettings.myFeedRubrics ?? []
  $: selectedAuthors = $userSettings.myFeedAuthors ?? []
  $: selectedMyFeedTags = $userSettings.myFeedTags ?? []
  $: selectedMyFeedComuns = $userSettings.myFeedComuns ?? []
  $: selectedMyFeedComunCategories = $userSettings.myFeedComunCategories ?? {}
  $: myFeedHasBaseSettings =
    selectedRubrics.length > 0 ||
    selectedAuthors.length > 0 ||
    selectedMyFeedTags.length > 0 ||
    selectedMyFeedComuns.length > 0
  $: hiddenAuthorKeys = new Set(
    ($userSettings.hiddenAuthors ?? []).map((value) => value.toLowerCase())
  )
  $: canLoadMyFeed =
    feedType === 'mine' && $siteUser && $feedSettingsHydrated && myFeedHasBaseSettings
  $: hideNegativeMyFeed = $userSettings.myFeedHideNegative ?? true
  $: hideReadPosts = ($userSettings.hideReadPosts ?? false) && !!$siteUser
  $: effectiveHideRead = hideReadPosts && !readOnly
  $: visiblePosts = posts.filter(isAuthorVisible) as BackendPost[]

  $: if (feedType === 'mine' && browser && !myFeedSectionModulePromise) {
    myFeedSectionModulePromise = import('$lib/components/feeds/MyFeedSection.svelte')
  }

  $: if (data?.feedType && data.feedType !== lastFeedType && feedParam) {
    lastFeedType = data.feedType
    feedType = data.feedType ?? 'hot'
    thematicFeedMeta = feedType === 'thematic' ? null : thematicFeedMeta
    if (feedType === 'mine' || feedType === 'favorites') {
      posts = []
      offset = 0
      hasMore = false
      loadingMore = false
      hiddenReadCount = 0
      thematicFeedMeta = null
      lastMyFeedKey = ''
    } else {
      posts = data.posts ?? []
      thematicFeedMeta = feedType === 'thematic' ? (data.thematicFeed ?? null) : thematicFeedMeta
      offset = posts.length
      hasMore = posts.length === pageSize
      loadingMore = false
      hiddenReadCount = 0
      if (feedType !== 'thematic') {
        thematicFeedMeta = null
      }
    }
  }

  $: if (!feedParam) {
    const preferredFeed = $userSettings.homeFeed ?? 'hot'
    if (preferredFeed !== feedType) {
      feedType = preferredFeed
      lastFeedType = preferredFeed
      thematicFeedMeta = feedType === 'thematic' ? null : thematicFeedMeta
      if (feedType === 'mine' || feedType === 'favorites') {
        posts = []
        offset = 0
        hasMore = false
        loadingMore = false
        hiddenReadCount = 0
        thematicFeedMeta = null
        lastMyFeedKey = ''
      } else {
        posts = []
        offset = 0
        hasMore = true
        loadingMore = false
        hiddenReadCount = 0
        if (feedType !== 'thematic') {
          thematicFeedMeta = null
        }
        if (browser) {
          void loadMore()
        }
      }
    }
  }

  $: if (feedType !== 'mine' && feedType !== 'favorites') {
    const feedKey = [
      feedType,
      feedType === 'thematic' ? thematicFeedSlug || '(none)' : '',
      readOnly ? 'only-read' : effectiveHideRead ? 'hide-read' : 'all',
      hideNegativeMyFeed ? 'hide-neg' : 'show-neg',
    ].join('|')
    if (lastFeedKey === null) {
      lastFeedKey = feedKey
      if ((effectiveHideRead || readOnly) && browser) {
        posts = []
        offset = 0
        hasMore = true
        loadingMore = false
        hiddenReadCount = 0
        void loadMore()
      }
    } else if (feedKey !== lastFeedKey) {
      lastFeedKey = feedKey
      posts = []
      offset = 0
      hasMore = true
      loadingMore = false
      hiddenReadCount = 0
      if (browser) {
        void loadMore()
      }
    }
  }

  $: if (feedType === 'mine') {
    const authKey = $siteUser ? 'auth' : 'anon'
    const hydrationKey = $siteUser ? ($feedSettingsHydrated ? 'settings-ready' : 'settings-loading') : 'no-settings'
    const key = `${authKey}:${hydrationKey}:${selectedRubrics.join(',')}:${selectedAuthors.join(',')}:${selectedMyFeedTags.join(',')}:${selectedMyFeedComuns.join(',')}:${JSON.stringify(selectedMyFeedComunCategories)}:${hideNegativeMyFeed ? 'no-negative' : 'all'}:${readOnly ? 'only-read' : effectiveHideRead ? 'hide-read' : 'all-read'}`
    if (key !== lastMyFeedKey) {
      lastMyFeedKey = key
      posts = []
      offset = 0
      hasMore = false
      loadingMore = false
      hiddenReadCount = 0
      if (canLoadMyFeed) {
        hasMore = true
        void loadMore()
      }
    }
  }

  $: if (feedType === 'favorites') {
    const authKey = $siteUser ? 'auth' : 'anon'
    const key = `favorites:${authKey}`
    if (key !== lastMyFeedKey) {
      lastMyFeedKey = key
      posts = []
      offset = 0
      hasMore = !!$siteUser
      loadingMore = false
      hiddenReadCount = 0
      if ($siteUser && browser) {
        void loadMore()
      }
    }
  }

  $: siteBaseUrl = (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '')
  $: canonicalUrl = `${siteBaseUrl}/`
</script>

<div class="flex max-w-full min-w-0 w-full flex-col gap-2">
  <header class="relative flex flex-col gap-2">
    {#if feedType === 'thematic'}
      <div class="flex flex-col gap-2">
        <h1 class="text-2xl font-semibold text-slate-900 dark:text-zinc-100">
          {#if thematicFeedMeta?.name}
            Папка: {thematicFeedMeta.name}
          {:else}
            Папка
          {/if}
        </h1>
        {#if thematicFeedMeta?.description}
          <div class="text-sm text-slate-600 dark:text-zinc-300">
            {thematicFeedMeta.description}
          </div>
        {/if}
        {#if thematicFeedMeta}
          <div class="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              class="inline-flex items-center rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 dark:bg-zinc-100 dark:text-zinc-950 dark:hover:bg-zinc-200"
              on:click={applyThematicFeedToMyFeed}
            >
              Сделать моей лентой
            </button>
            {#if canManageCurrentFolder()}
              <button
                type="button"
                class="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
                on:click={openCurrentFolderSettings}
              >
                <Icon src={Cog6Tooth} size="16" mini />
                <span>Настройки</span>
              </button>
            {/if}
          </div>
        {/if}
      </div>
    {:else if feedType === 'favorites'}
      <h1 class="text-2xl font-semibold text-slate-900 dark:text-zinc-100">
        Избранное
      </h1>
    {:else if feedType !== 'mine'}
      <Header pageHeader>
        {$t('routes.frontpage.title')}
      </Header>
    {/if}
  </header>

  {#if folderSettingsModalModulePromise}
    {#await folderSettingsModalModulePromise then module}
      <svelte:component
        this={module.default}
        open={folderSettingsOpen}
        {thematicFeedSlug}
        onClose={closeCurrentFolderSettings}
        onUpdatedFolder={onThematicFeedUpdated}
        onRefreshFeed={refreshCurrentFolderFeedAfterSettingsSave}
      />
    {/await}
  {/if}

  {#if $siteUser && readOnly && feedType !== 'favorites'}
    <div class="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900">
      <div class="text-sm text-slate-600 dark:text-zinc-300">
        Показываем только прочитанные посты
      </div>
      <button
        type="button"
        class="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
        on:click={closeReadPosts}
      >
        Вернуться
      </button>
    </div>
  {:else if $siteUser && feedType !== 'favorites' && effectiveHideRead && hiddenReadCount > 0}
    <div class="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900">
      <div class="text-sm text-slate-600 dark:text-zinc-300">
        {hiddenReadCount} прочитанных постов скрыто
      </div>
      <button
        type="button"
        class="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
        on:click={openReadPosts}
      >
        Показать
      </button>
    </div>
  {/if}

  {#if feedType === 'mine'}
    {#if myFeedSectionModulePromise}
      {#await myFeedSectionModulePromise then module}
        <svelte:component this={module.default} {posts} {loadingMore} />
      {/await}
    {/if}
  {:else if feedType === 'favorites' && !$siteUser}
    <div class="text-base text-slate-500">
      После регистрации вы сможете добавлять посты в избранное и видеть их в отдельной ленте.
    </div>
  {:else if feedType === 'thematic' && !thematicFeedSlug}
    <div class="text-base text-slate-500">
      Выберите папку в левом меню, чтобы посмотреть готовую подборку авторов и фильтров по тегам.
    </div>
  {:else if visiblePosts.length}
    <FeedPostsList posts={visiblePosts} {loadingMore} />
  {:else}
    <div class="text-base text-slate-500">Пока нет публикаций.</div>
  {/if}
</div>

<svelte:head>
  <title>Самые новые и обсуждаемые посты лучших telegram каналов</title>
  <meta name="description" content={env.PUBLIC_SITE_DESCRIPTION} />
  <meta property="og:title" content={env.PUBLIC_OG_TITLE} />
  <meta property="og:description" content={env.PUBLIC_OG_DESCRIPTION} />
  <meta property="og:image" content={env.PUBLIC_OG_IMAGE} />
  <meta property="og:url" content={env.PUBLIC_OG_URL} />
  <meta property="og:type" content="website" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={env.PUBLIC_TWITTER_TITLE} />
  <meta name="twitter:description" content={env.PUBLIC_TWITTER_DESCRIPTION} />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
