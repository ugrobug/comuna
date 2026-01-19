<script lang="ts" context="module">
</script>

<script lang="ts">
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { t } from '$lib/translations.js'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { backendPostToPostView, buildBackendPostPath, buildHomeFeedUrl } from '$lib/api/backend'
  import { afterUpdate, onDestroy, tick } from 'svelte'

  export let data

  const pageSize = 10
  const prefetchOffset = 3
  let posts = data.posts ?? []
  let hasMore = posts.length === pageSize
  let loadingMore = false
  let sentinel: HTMLElement | null = null
  let observer: IntersectionObserver | null = null
  $: prefetchIndex = Math.max(posts.length - prefetchOffset, 0)
  $: if (data?.posts) {
    posts = data.posts ?? []
    hasMore = posts.length === pageSize
    loadingMore = false
    observer?.disconnect()
    observer = null
  }

  // Определяем канонический URL для главной страницы
  $: siteBaseUrl = (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '')
  $: canonicalUrl = `${siteBaseUrl}/`

  const buildPageUrl = (offset: number) => {
    const url = new URL(buildHomeFeedUrl())
    url.searchParams.set('limit', String(pageSize))
    url.searchParams.set('offset', String(offset))
    return url.toString()
  }

  const loadMore = async () => {
    if (loadingMore || !hasMore) return
    loadingMore = true
    try {
      const response = await fetch(buildPageUrl(posts.length))
      if (!response.ok) {
        hasMore = false
        return
      }
      const payload = await response.json()
      const nextPosts = payload.posts ?? []
      if (nextPosts.length) {
        posts = [...posts, ...nextPosts]
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

  const setupObserver = async () => {
    if (!browser) return
    await tick()
    if (observer) {
      observer.disconnect()
      observer = null
    }
    if (!sentinel || !hasMore) return
    observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          loadMore()
        }
      },
      { threshold: 0.1 }
    )
    observer.observe(sentinel)
  }

  afterUpdate(() => {
    if (browser) {
      setupObserver()
    }
  })

  onDestroy(() => {
    observer?.disconnect()
  })
</script>
<div class="flex flex-col gap-2 max-w-full w-full min-w-0">
  <header class="flex flex-col gap-4 relative">
    <Header pageHeader>
      {$t('routes.frontpage.title')}
    </Header>
  </header>
  {#if posts?.length}
    <div class="flex flex-col gap-6">
      {#each posts as backendPost, index (backendPost.id)}
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
        {#if index === prefetchIndex}
          <div bind:this={sentinel} class="h-px"></div>
        {/if}
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
