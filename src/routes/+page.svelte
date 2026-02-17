<script lang="ts" context="module">
</script>

	<script lang="ts">
	  import { browser } from '$app/environment'
	  import { goto } from '$app/navigation'
	  import { page } from '$app/stores'
	  import { env } from '$env/dynamic/public'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { t } from '$lib/translations.js'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import {
    backendPostToPostView,
    buildBackendPostPath,
    buildFreshFeedUrl,
    buildHomeFeedUrl,
    buildMyFeedUrl,
    buildTagsListUrl,
  } from '$lib/api/backend'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import { userSettings } from '$lib/settings'
  import { normalizeTag } from '$lib/tags'
  import { Button } from 'mono-svelte'
  import { onDestroy, onMount } from 'svelte'
  import { Cog6Tooth, Icon } from 'svelte-hero-icons'

  export let data

  const pageSize = 10
  let feedType = data.feedType ?? 'hot'
  let posts = data.posts ?? []
  let filteredMyFeedPosts = posts
  let offset = posts.length
  let hasMore = posts.length === pageSize
  let loadingMore = false
  let lastPostsRef = data.posts
  let lastFeedType = feedType
  let lastMyFeedKey = ''
	  let lastFeedKey: string | null = null
	  let myFeedSettingsOpen = false
	  let feedParam: string | null = null
	  let readParam: string | null = null
	  let readOnly = false
	  let hiddenReadCount = 0
  const moodDurationMs = 3 * 60 * 60 * 1000
  const moodOptions: Array<{ label: string; value: 'funny' | 'serious' | 'sad' }> = [
    { label: 'Веселое', value: 'funny' },
    { label: 'Серьезное', value: 'serious' },
    { label: 'Грустное', value: 'sad' },
  ]
  let myFeedMood: 'funny' | 'serious' | 'sad' | null = null
  let myFeedMoodExpiresAt: number | null = null
  let moodActive = false
  let effectiveMood: 'funny' | 'serious' | 'sad' | null = null
  let moodTagSet = new Set<string>()
  let tagMoodMap = new Map<string, string>()
  let tagLemmaMap = new Map<string, string>()
  let tagMoodLoading = false
  let moodExpiryTimer: ReturnType<typeof setTimeout> | null = null
  $: if (data?.posts) {
    if (data.posts !== lastPostsRef && data.feedType === feedType && data.feedType !== 'mine') {
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
	  $: if (data?.feedType && data.feedType !== lastFeedType && feedParam) {
	    lastFeedType = data.feedType
	    feedType = data.feedType ?? 'hot'
	    if (feedType === 'mine') {
	      posts = []
	      offset = 0
	      hasMore = false
	      loadingMore = false
	      hiddenReadCount = 0
	      lastMyFeedKey = ''
	    } else {
	      posts = data.posts ?? []
	      offset = posts.length
	      hasMore = posts.length === pageSize
	      loadingMore = false
	      hiddenReadCount = 0
	    }
	  }
	  $: if (!feedParam) {
	    const preferredFeed = $userSettings.homeFeed ?? 'hot'
	    if (preferredFeed !== feedType) {
	      feedType = preferredFeed
	      lastFeedType = preferredFeed
	      if (feedType === 'mine') {
	        posts = []
	        offset = 0
	        hasMore = false
	        loadingMore = false
	        hiddenReadCount = 0
	        lastMyFeedKey = ''
	      } else {
	        posts = []
	        offset = 0
	        hasMore = true
	        loadingMore = false
	        hiddenReadCount = 0
	        if (browser) {
	          loadMore()
	        }
	      }
	    }
	  }
  const scrollThreshold = 400
  let scrollRaf: number | null = null

  $: selectedRubrics = $userSettings.myFeedRubrics ?? []
  $: selectedAuthors = $userSettings.myFeedAuthors ?? []
  $: canLoadMyFeed =
    feedType === 'mine' &&
    $siteUser &&
    (selectedRubrics.length > 0 || selectedAuthors.length > 0)
	  $: hideNegativeMyFeed = $userSettings.myFeedHideNegative ?? true
	  $: hideReadPosts = ($userSettings.hideReadPosts ?? false) && !!$siteUser
	  $: effectiveHideRead = hideReadPosts && !readOnly
	  $: myFeedMood = $userSettings.myFeedMood ?? null
  $: myFeedMoodExpiresAt = $userSettings.myFeedMoodExpiresAt ?? null
  $: moodActive =
    !!myFeedMood &&
    !!myFeedMoodExpiresAt &&
    Date.now() < myFeedMoodExpiresAt
  $: effectiveMood = moodActive ? myFeedMood : null
  // Определяем канонический URL для главной страницы
  $: siteBaseUrl = (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '')
  $: canonicalUrl = `${siteBaseUrl}/`

	  const buildPageUrl = (offset: number) => {
	    let baseUrl = buildHomeFeedUrl({
	      hideRead: effectiveHideRead,
	      onlyRead: readOnly,
	    })
	    if (feedType === 'fresh') {
	      baseUrl = buildFreshFeedUrl({
	        hideRead: effectiveHideRead,
	        onlyRead: readOnly,
	      })
	    } else if (feedType === 'mine') {
	      baseUrl = buildMyFeedUrl(
	        selectedRubrics,
	        selectedAuthors,
	        hideNegativeMyFeed,
	        effectiveHideRead,
	        readOnly
	      )
	    }
	    const url = new URL(baseUrl)
	    url.searchParams.set('limit', String(pageSize))
	    url.searchParams.set('offset', String(offset))
    return url.toString()
  }

	  $: if (feedType !== 'mine') {
	    const feedKey = [
	      feedType,
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
	        loadMore()
	      }
	    } else if (feedKey !== lastFeedKey) {
	      lastFeedKey = feedKey
	      posts = []
	      offset = 0
	      hasMore = true
	      loadingMore = false
	      hiddenReadCount = 0
	      if (browser) {
	        loadMore()
	      }
	    }
	  }

	  const loadMore = async () => {
	    if (!browser || loadingMore || !hasMore) return
	    if (feedType === 'mine' && !canLoadMyFeed) return
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

  const openMyFeedSettings = () => {
    myFeedSettingsOpen = true
  }

  const toggleMyFeedSettings = () => {
    if (myFeedSettingsOpen) {
      myFeedSettingsOpen = false
    } else {
      openMyFeedSettings()
    }
  }

	  const resetMyFeed = () => {
	    posts = []
	    offset = 0
	    hasMore = false
	    loadingMore = false
	    hiddenReadCount = 0
	    if (canLoadMyFeed) {
	      hasMore = true
	      loadMore()
	    }
	  }

  const loadTagMoods = async () => {
    if (!browser || tagMoodLoading || tagMoodMap.size) return
    tagMoodLoading = true
    try {
      const response = await fetch(buildTagsListUrl())
      if (response.ok) {
        const payload = await response.json()
        const entries =
          payload.tags?.map((tag: { name: string; lemma?: string; mood: string }) => [
            normalizeTag(tag.lemma ?? tag.name),
            tag.mood,
          ]) ?? []
        const lemmaEntries =
          payload.tags?.map((tag: { name: string; lemma?: string }) => [
            normalizeTag(tag.name),
            normalizeTag(tag.lemma ?? tag.name),
          ]) ?? []
        tagMoodMap = new Map(entries)
        tagLemmaMap = new Map(lemmaEntries)
      }
    } catch (error) {
      console.error('Failed to load tag moods:', error)
    } finally {
      tagMoodLoading = false
    }
  }

  const selectMood = (value: 'funny' | 'serious' | 'sad') => {
    if (moodActive && myFeedMood === value) {
      clearMood()
      return
    }
    const expiresAt = Date.now() + moodDurationMs
    $userSettings = {
      ...$userSettings,
      myFeedMood: value,
      myFeedMoodExpiresAt: expiresAt,
    }
  }

  const clearMood = () => {
    $userSettings = {
      ...$userSettings,
      myFeedMood: null,
      myFeedMoodExpiresAt: null,
    }
  }

  const scheduleMoodClear = (expiresAt: number | null) => {
    if (!browser) return
    if (moodExpiryTimer) {
      window.clearTimeout(moodExpiryTimer)
      moodExpiryTimer = null
    }
    if (!expiresAt) return
    const delay = expiresAt - Date.now()
    if (delay <= 0) {
      userSettings.update((settings) => ({
        ...settings,
        myFeedMood: null,
        myFeedMoodExpiresAt: null,
      }))
      return
    }
    moodExpiryTimer = window.setTimeout(() => {
      userSettings.update((settings) => ({
        ...settings,
        myFeedMood: null,
        myFeedMoodExpiresAt: null,
      }))
    }, delay)
  }


  $: moodTagSet =
    effectiveMood && tagMoodMap.size
      ? new Set(
          Array.from(tagMoodMap.entries())
            .filter(([, mood]) => mood === effectiveMood)
            .map(([name]) => name)
        )
      : new Set<string>()

  $: filteredMyFeedPosts =
    effectiveMood && tagMoodMap.size
      ? posts.filter((post) =>
          (post.tags ?? []).some((tag) => {
            const rawName = typeof tag === 'string' ? tag : tag.name
            const normalized = normalizeTag(rawName)
            const lemma =
              typeof tag === 'string'
                ? tagLemmaMap.get(normalized) ?? normalized
                : normalizeTag(tag.lemma ?? tag.name)
            return moodTagSet.has(lemma)
          })
        )
      : effectiveMood
        ? []
        : posts

  $: if (feedType === 'mine') {
    const authKey = $siteUser ? 'auth' : 'anon'
	    const key = `${authKey}:${selectedRubrics.join(',')}:${selectedAuthors.join(',')}:${hideNegativeMyFeed ? 'no-negative' : 'all'}:${readOnly ? 'only-read' : effectiveHideRead ? 'hide-read' : 'all-read'}`
    if (key !== lastMyFeedKey) {
      lastMyFeedKey = key
      resetMyFeed()
    }
    if (effectiveMood) {
      loadTagMoods()
    }
  }

  const maybeLoadMore = () => {
    if (!browser || loadingMore || !hasMore) return
    const viewportBottom = window.scrollY + window.innerHeight
    const pageHeight = document.documentElement.scrollHeight
    if (pageHeight - viewportBottom <= scrollThreshold) {
      loadMore()
    }
  }

  const onScroll = () => {
    if (scrollRaf !== null) return
    scrollRaf = window.requestAnimationFrame(() => {
      scrollRaf = null
      maybeLoadMore()
    })
  }

  onMount(() => {
    if (!browser) return
    maybeLoadMore()
    const unsubscribe = userSettings.subscribe((settings) => {
      scheduleMoodClear(settings.myFeedMoodExpiresAt ?? null)
    })
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      unsubscribe()
    }
  })

  onDestroy(() => {
    if (browser) {
      window.removeEventListener('scroll', onScroll)
      if (scrollRaf !== null) {
        window.cancelAnimationFrame(scrollRaf)
        scrollRaf = null
      }
      if (moodExpiryTimer) {
        window.clearTimeout(moodExpiryTimer)
        moodExpiryTimer = null
      }
    }
  })

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
</script>
<div class="flex flex-col gap-2 max-w-full w-full min-w-0">
  <header class="flex flex-col gap-2 relative">
    {#if feedType === 'mine'}
      <h1 class="text-2xl font-semibold text-slate-900 dark:text-zinc-100">
        Моя лента
      </h1>
      {#if $siteUser}
        <button
          type="button"
          class="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 dark:text-zinc-400 dark:hover:text-zinc-200"
          on:click={toggleMyFeedSettings}
          aria-expanded={myFeedSettingsOpen}
        >
          <Icon src={Cog6Tooth} size="16" mini />
          <span>Настроить</span>
        </button>
      {/if}
    {:else}
      <Header pageHeader>
        {$t('routes.frontpage.title')}
      </Header>
    {/if}
  </header>
  {#if $siteUser && readOnly}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-4 py-3 flex items-center justify-between gap-3">
      <div class="text-sm text-slate-600 dark:text-zinc-300">
        Показываем только прочитанные посты
      </div>
      <button
        type="button"
        class="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
        on:click={closeReadPosts}
      >
        Вернуться
      </button>
    </div>
  {:else if $siteUser && effectiveHideRead && hiddenReadCount > 0}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-4 py-3 flex items-center justify-between gap-3">
      <div class="text-sm text-slate-600 dark:text-zinc-300">
        {hiddenReadCount} прочитанных постов скрыто
      </div>
      <button
        type="button"
        class="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
        on:click={openReadPosts}
      >
        Показать
      </button>
    </div>
  {/if}
  {#if feedType === 'mine' && !$siteUser}
    <div class="text-base text-slate-500">
      После регистрации вы получите доступ к персонализируемой ленте, которую сможете настроить и видеть только интересные вам посты.
    </div>
  {:else if feedType === 'mine' && $siteUser}
    <div class="flex flex-col gap-4">
      {#if myFeedSettingsOpen}
        <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 flex flex-col gap-4">
          <div class="flex flex-wrap gap-2">
            {#each moodOptions as mood}
              <Button
                color={effectiveMood === mood.value ? 'primary' : 'ghost'}
                on:click={() => selectMood(mood.value)}
              >
                {mood.label}
              </Button>
            {/each}
          </div>
          <div class="text-xs text-slate-500 dark:text-zinc-400">
            Можно быстро настроить ленту под настроение на 3 часа — действует в текущей сессии.
          </div>
          <div class="text-sm text-slate-600 dark:text-zinc-300">
            Выбор рубрик и составление черного списка доступны в настройках сайта.
          </div>
          <a href="/settings" class="text-sm text-blue-600 dark:text-blue-400 hover:underline">
            Перейти в настройки
          </a>
        </div>
      {:else}
        {#if !selectedRubrics.length && !selectedAuthors.length}
          <div class="text-sm text-slate-500 dark:text-zinc-400">
            Чтобы лента заработала, выберите рубрики в настройках сайта или добавьте авторов на их страницах.
          </div>
        {/if}
      {/if}
      {#if effectiveMood && tagMoodLoading}
        <div class="text-sm text-slate-500">Загружаем теги настроения...</div>
      {/if}
      {#if filteredMyFeedPosts?.length}
        <div class="flex flex-col gap-6">
          {#each filteredMyFeedPosts as backendPost (backendPost.id)}
            {@const postView = backendPostToPostView(backendPost, backendPost.author)}
            <Post
              post={postView}
              view="cozy"
              actions={true}
              showReadMore={false}
              showFullBody={false}
              linkOverride={buildBackendPostPath(backendPost)}
              userUrlOverride={backendPost.author?.username ? `/${backendPost.author.username}` : undefined}
              communityUrlOverride={backendPost.rubric_slug ? `/rubrics/${backendPost.rubric_slug}/posts` : undefined}
              subscribeUrl={backendPost.channel_url ?? backendPost.author?.channel_url}
              subscribeLabel="Подписаться"
            />
          {/each}
        </div>
        {#if loadingMore}
          <div class="text-sm text-slate-500">Загрузка...</div>
        {/if}
      {:else}
        <div class="text-base text-slate-500">Пока нет публикаций.</div>
      {/if}
    </div>
  {:else if posts?.length}
    <div class="flex flex-col gap-6">
      {#each posts as backendPost (backendPost.id)}
        {@const postView = backendPostToPostView(backendPost, backendPost.author)}
        <Post
          post={postView}
          view="cozy"
          actions={true}
          showReadMore={false}
          showFullBody={false}
          linkOverride={buildBackendPostPath(backendPost)}
          userUrlOverride={backendPost.author?.username ? `/${backendPost.author.username}` : undefined}
          communityUrlOverride={backendPost.rubric_slug ? `/rubrics/${backendPost.rubric_slug}/posts` : undefined}
          subscribeUrl={backendPost.channel_url ?? backendPost.author?.channel_url}
          subscribeLabel="Подписаться"
        />
      {/each}
    </div>
    {#if loadingMore}
      <div class="text-sm text-slate-500">Загрузка...</div>
    {/if}
  {:else}
    <div class="text-base text-slate-500">Пока нет публикаций.</div>
  {/if}
</div>

<svelte:head>
  <title>Самые новые и обсуждаемые посты лучших telegram каналов</title>
  <meta name="description" content={env.PUBLIC_SITE_DESCRIPTION} />
  
  <!-- Open Graph теги -->
  <meta property="og:title" content={env.PUBLIC_OG_TITLE} />
  <meta property="og:description" content={env.PUBLIC_OG_DESCRIPTION} />
  <meta property="og:image" content={env.PUBLIC_OG_IMAGE} />
  <meta property="og:url" content={env.PUBLIC_OG_URL} />
  <meta property="og:type" content="website" />
  
  <!-- Twitter теги -->
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={env.PUBLIC_TWITTER_TITLE} />
  <meta name="twitter:description" content={env.PUBLIC_TWITTER_DESCRIPTION} />
  
  <!-- Дополнительные мета-теги -->
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
