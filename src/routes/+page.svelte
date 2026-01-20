<script lang="ts" context="module">
</script>

<script lang="ts">
  import { browser } from '$app/environment'
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
    buildRubricsUrl,
  } from '$lib/api/backend'
  import { siteUser } from '$lib/siteAuth'
  import { userSettings } from '$lib/settings'
  import { Button } from 'mono-svelte'
  import { onDestroy, onMount } from 'svelte'

  export let data

  const pageSize = 10
  let feedType = data.feedType ?? 'hot'
  let posts = data.posts ?? []
  let offset = posts.length
  let hasMore = posts.length === pageSize
  let loadingMore = false
  let lastPostsRef = data.posts
  let lastFeedType = feedType
  let lastMyFeedKey = ''
  let rubrics: Array<{ name: string; slug: string; icon_url?: string | null }> = []
  let rubricsLoading = false
  $: if (data?.posts) {
    if (data.posts !== lastPostsRef && data.feedType !== 'mine') {
      lastPostsRef = data.posts
      posts = data.posts ?? []
      offset = posts.length
      hasMore = posts.length === pageSize
      loadingMore = false
    }
  }
  $: if (data?.feedType && data.feedType !== lastFeedType) {
    lastFeedType = data.feedType
    feedType = data.feedType ?? 'hot'
    if (feedType === 'mine') {
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
  const scrollThreshold = 400
  let scrollRaf: number | null = null

  $: selectedRubrics = $userSettings.myFeedRubrics ?? []
  $: canLoadMyFeed = feedType === 'mine' && $siteUser && selectedRubrics.length > 0

  // Определяем канонический URL для главной страницы
  $: siteBaseUrl = (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '')
  $: canonicalUrl = `${siteBaseUrl}/`

  const buildPageUrl = (offset: number) => {
    let baseUrl = buildHomeFeedUrl()
    if (feedType === 'fresh') {
      baseUrl = buildFreshFeedUrl()
    } else if (feedType === 'mine') {
      baseUrl = buildMyFeedUrl(selectedRubrics)
    }
    const url = new URL(baseUrl)
    url.searchParams.set('limit', String(pageSize))
    url.searchParams.set('offset', String(offset))
    return url.toString()
  }

  const loadMore = async () => {
    if (loadingMore || !hasMore) return
    if (feedType === 'mine' && !canLoadMyFeed) return
    loadingMore = true
    try {
      const response = await fetch(buildPageUrl(offset))
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
      if (nextPosts.length < pageSize) {
        hasMore = false
      }
    } catch (error) {
      console.error('Failed to load more posts:', error)
    } finally {
      loadingMore = false
    }
  }

  const loadRubrics = async () => {
    if (rubricsLoading || rubrics.length) return
    rubricsLoading = true
    try {
      const response = await fetch(buildRubricsUrl())
      if (response.ok) {
        const data = await response.json()
        rubrics = data.rubrics ?? []
      }
    } catch (error) {
      console.error('Failed to load rubrics:', error)
    } finally {
      rubricsLoading = false
    }
  }

  const toggleRubric = (slug: string) => {
    const current = new Set(selectedRubrics)
    if (current.has(slug)) {
      current.delete(slug)
    } else {
      current.add(slug)
    }
    $userSettings = { ...$userSettings, myFeedRubrics: Array.from(current) }
  }

  const resetMyFeed = () => {
    posts = []
    offset = 0
    hasMore = false
    loadingMore = false
    if (canLoadMyFeed) {
      hasMore = true
      loadMore()
    }
  }

  $: if (feedType === 'mine') {
    const authKey = $siteUser ? 'auth' : 'anon'
    const key = `${authKey}:${selectedRubrics.join(',')}`
    if (key !== lastMyFeedKey) {
      lastMyFeedKey = key
      resetMyFeed()
    }
    if (!rubrics.length && !rubricsLoading) {
      loadRubrics()
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
    window.addEventListener('scroll', onScroll, { passive: true })
  })

  onDestroy(() => {
    if (browser) {
      window.removeEventListener('scroll', onScroll)
      if (scrollRaf !== null) {
        window.cancelAnimationFrame(scrollRaf)
        scrollRaf = null
      }
    }
  })
</script>
<div class="flex flex-col gap-2 max-w-full w-full min-w-0">
  <header class="flex flex-col gap-4 relative">
    <Header pageHeader>
      {$t('routes.frontpage.title')}
    </Header>
  </header>
  {#if feedType === 'mine' && !$siteUser}
    <div class="text-base text-slate-500">
      После регистрации вы получите доступ к персонализируемой ленте, которую сможете настроить и видеть только интересные вам посты.
    </div>
  {:else if feedType === 'mine' && !selectedRubrics.length}
    <div class="flex flex-col gap-4">
      <div class="text-base text-slate-600 dark:text-zinc-300">
        Выберите рубрики, которые хотите видеть в своей ленте. Эти настройки всегда можно поменять в настройках сайта.
      </div>
      {#if rubricsLoading}
        <div class="text-sm text-slate-500">Загружаем рубрики...</div>
      {:else if rubrics.length}
        <div class="flex flex-col gap-3">
          {#each rubrics as rubric}
            <label class="flex items-center gap-3 text-sm text-slate-700 dark:text-zinc-200">
              <input
                class="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
                type="checkbox"
                checked={selectedRubrics.includes(rubric.slug)}
                on:change={() => toggleRubric(rubric.slug)}
              />
              <span>{rubric.name}</span>
            </label>
          {/each}
        </div>
        <div class="flex items-center gap-2">
          <Button color="primary" on:click={resetMyFeed}>
            Показать ленту
          </Button>
          <a href="/settings" class="text-sm text-blue-600 dark:text-blue-400 hover:underline">
            Настройки сайта
          </a>
        </div>
      {:else}
        <div class="text-sm text-slate-500">Рубрики пока не загружены.</div>
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
