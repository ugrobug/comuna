<script lang="ts">
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import { onDestroy, onMount } from 'svelte'
  import { Button, toast } from 'mono-svelte'
  import FeedPostsList from '$lib/components/feeds/FeedPostsList.svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { buildTagPostsUrl } from '$lib/api/backend'
  import { userSettings } from '$lib/settings'
  import { normalizeTag } from '$lib/tags'

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
  $: hiddenAuthorKeys = new Set(
    ($userSettings.hiddenAuthors ?? []).map((value) => value.toLowerCase())
  )

  $: tagName = data.tag?.name ?? data.tag ?? ''
  $: tagLemma = normalizeTag(data.tag?.lemma ?? tagName)
  $: tagKey = tagLemma
  $: isBlacklisted = Boolean(tagKey && $userSettings.tagRules?.[tagKey] === 'hide')

  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Тамбур'
  $: title = `Посты по тегу «${tagName}» — ${siteTitle}`
  $: description = `Посты по тегу «${tagName}» на ${siteTitle}.`
  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()

  const authorKey = (backendPost: { author?: { username?: string } }) =>
    (backendPost.author?.username ?? '').trim().toLowerCase()

  const isAuthorVisible = (backendPost: { author?: { username?: string } }) => {
    const key = authorKey(backendPost)
    if (!key) return true
    return !hiddenAuthorKeys.has(key)
  }

  $: visiblePosts = posts.filter(isAuthorVisible)

  const buildPageUrl = (offset: number) => {
    if (!tagName) return ''
    const url = new URL(buildTagPostsUrl(tagLemma || tagName), $page.url.origin)
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

  const toggleBlacklist = () => {
    if (!tagKey) return
    if (isBlacklisted) {
      userSettings.update((settings) => {
        const nextRules = { ...(settings.tagRules ?? {}) }
        delete nextRules[tagKey]
        return {
          ...settings,
          tagRules: nextRules,
        }
      })
      toast({
        content: 'Посты с этим тегом снова будут отображаться',
        type: 'success',
      })
      return
    }

    userSettings.update((settings) => ({
      ...settings,
      tagRules: {
        ...(settings.tagRules ?? {}),
        [tagKey]: 'hide',
      },
    }))
    toast({
      content: 'Посты с этим тегом больше не будут отображаться',
      type: 'success',
    })
  }
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Посты по тегу: «{tagName}»</h1>
  </Header>

  <div class="flex flex-wrap items-center gap-3">
    <Button
      size="sm"
      color="secondary"
      on:click={toggleBlacklist}
    >
      {isBlacklisted ? 'Убрать из черного списка' : 'Добавить тег в черный список'}
    </Button>
  </div>

  {#if visiblePosts?.length}
    <FeedPostsList posts={visiblePosts} {loadingMore} />
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
