<script lang="ts">
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import { onDestroy, onMount } from 'svelte'
  import { Button, toast } from 'mono-svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { backendPostToPostView, buildBackendPostPath, buildTagPostsUrl } from '$lib/api/backend'
  import { userSettings } from '$lib/settings'

  export let data

  const pageSize = 10
  let posts = data.posts ?? []
  let hasMore = posts.length === pageSize
  let loadingMore = false
  let lastPostsRef = data.posts
  $: if (data?.posts) {
    if (data.posts !== lastPostsRef) {
      lastPostsRef = data.posts
      posts = data.posts ?? []
      hasMore = posts.length === pageSize
      loadingMore = false
    }
  }
  const scrollThreshold = 400
  let scrollRaf: number | null = null

  $: tagName = data.tag?.name ?? data.tag ?? ''
  $: tagKey = tagName.trim().toLowerCase()
  $: isBlacklisted = Boolean(tagKey && $userSettings.tagRules?.[tagKey] === 'hide')

  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Comuna'
  $: title = `Посты по тегу «${tagName}» — ${siteTitle}`
  $: description = `Посты по тегу «${tagName}» на ${siteTitle}.`
  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()

  const buildPageUrl = (offset: number) => {
    if (!tagName) return ''
    const url = new URL(buildTagPostsUrl(tagName))
    url.searchParams.set('limit', String(pageSize))
    url.searchParams.set('offset', String(offset))
    return url.toString()
  }

  const loadMore = async () => {
    if (loadingMore || !hasMore) return
    const url = buildPageUrl(posts.length)
    if (!url) return
    loadingMore = true
    try {
      const response = await fetch(url)
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
      console.error('Failed to load more tag posts:', error)
    } finally {
      loadingMore = false
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

  const addToBlacklist = () => {
    if (!tagKey) return
    userSettings.update((settings) => {
      const next = { ...settings, tagRules: { ...settings.tagRules } }
      next.tagRules[tagKey] = 'hide'
      return next
    })
    toast({
      content: `Тег #${tagName} добавлен в черный список`,
      type: 'success',
    })
  }
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Посты по тегу «{tagName}»</h1>
  </Header>

  <div class="flex flex-wrap items-center gap-3">
    <Button
      size="sm"
      color="secondary"
      on:click={addToBlacklist}
      disabled={isBlacklisted}
    >
      {isBlacklisted ? 'Тег уже в черном списке' : 'Добавить тег в черный список'}
    </Button>
  </div>

  {#if posts?.length}
    <div class="flex flex-col gap-6">
      {#each posts as backendPost (backendPost.id)}
        {@const postView = backendPostToPostView(backendPost)}
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
    <div class="text-base text-slate-500">По этому тегу пока нет публикаций.</div>
  {/if}
</div>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
