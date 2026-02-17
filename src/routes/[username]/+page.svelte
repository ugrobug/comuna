<script lang="ts">
  import { browser } from '$app/environment'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { backendPostToPostView, buildAuthorPostsUrl, buildBackendPostPath } from '$lib/api/backend'
  import { env } from '$env/dynamic/public'
  import { siteUser } from '$lib/siteAuth'
  import { userSettings } from '$lib/settings'
  import { page } from '$app/stores'
  import { onDestroy, onMount } from 'svelte'

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

  const formatNumber = (value: number | undefined) => {
    if (!value && value !== 0) return '—'
    return value.toLocaleString('ru-RU')
  }

  $: authorUsername = data.author?.username ?? ''
  $: authorInMyFeed = Boolean(
    authorUsername && ($userSettings.myFeedAuthors ?? []).includes(authorUsername)
  )

  const toggleAuthorMyFeed = () => {
    if (!authorUsername || !$siteUser) return
    const current = new Set($userSettings.myFeedAuthors ?? [])
    if (current.has(authorUsername)) {
      current.delete(authorUsername)
    } else {
      current.add(authorUsername)
    }
    $userSettings = { ...$userSettings, myFeedAuthors: Array.from(current) }
  }

  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Comuna'
  $: authorName = data.author?.title ?? data.author?.username ?? ''
  $: title = authorName ? `${authorName} — ${siteTitle}` : siteTitle
  $: description =
    data.author?.description ||
    (authorName ? `Посты и материалы из Telegram-канала ${authorName}.` : '')
  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()

  const buildPageUrl = (offset: number) => {
    const username = data.author?.username
    if (!username) return ''
    const url = new URL(buildAuthorPostsUrl(username))
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
      console.error('Failed to load more author posts:', error)
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
</script>

<div class="flex flex-col gap-6 max-w-5xl">
  <section class="flex flex-col gap-6">
    <div class="flex flex-col lg:flex-row gap-8 items-start">
      <div class="flex flex-col items-center gap-4 shrink-0">
        <div class="w-40 h-40 rounded-full overflow-hidden border-4 border-white dark:border-zinc-900 bg-slate-100 dark:bg-zinc-800">
          {#if data.author?.avatar_url}
            <img src={data.author.avatar_url} alt={data.author?.title ?? data.author?.username} class="w-full h-full object-cover" />
          {:else}
            <div class="w-full h-full flex items-center justify-center text-4xl font-bold text-slate-400 dark:text-zinc-500">
              {data.author?.title?.[0] ?? data.author?.username?.[0] ?? 'A'}
            </div>
          {/if}
        </div>
        {#if data.author?.channel_url}
          <a
            class="inline-flex items-center justify-center w-12 h-12 rounded-full bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700"
            href={data.author.channel_url}
            target="_blank"
            rel="nofollow noopener"
          >
            <img src="/img/logos/telegram_logo.svg" alt="Telegram" class="w-6 h-6" />
          </a>
        {/if}
      </div>

      <div class="flex flex-col gap-4 max-w-2xl">
        <div class="text-3xl font-bold text-slate-900 dark:text-zinc-50">
          {data.author?.title ?? data.author?.username}
        </div>
        <div class="flex flex-wrap items-center gap-3 text-sm text-slate-600 dark:text-zinc-400">
          <span class="px-4 py-2 rounded-full bg-slate-100 dark:bg-zinc-800">
            {formatNumber(data.author?.subscribers_count)} подписчиков
          </span>
          <span class="px-4 py-2 rounded-full bg-slate-100 dark:bg-zinc-800">
            {formatNumber(data.author?.posts_count)} постов
          </span>
          {#if data.author?.author_rating !== undefined}
            <span class="px-4 py-2 rounded-full bg-slate-100 dark:bg-zinc-800">
              Рейтинг {formatNumber(data.author?.author_rating)}
            </span>
          {/if}
        </div>
        {#if $siteUser && authorUsername}
          <button
            type="button"
            class="inline-flex w-fit items-center gap-2 rounded-xl border border-slate-300 dark:border-zinc-700 px-4 py-2 text-sm font-medium text-slate-700 dark:text-zinc-200 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
            on:click={toggleAuthorMyFeed}
          >
            {authorInMyFeed ? 'Убрать из моей ленты' : 'Добавить в мою ленту'}
          </button>
        {/if}
        {#if data.author?.description}
          <p class="text-lg leading-relaxed text-slate-700 dark:text-zinc-300">
            {data.author.description}
          </p>
        {/if}
      </div>
    </div>
  </section>

  <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Посты</div>

  {#if posts?.length}
    <div class="flex flex-col gap-6">
      {#each posts as backendPost (backendPost.id)}
        {@const postView = backendPostToPostView(backendPost, data.author)}
        <Post
          post={postView}
          view="cozy"
          actions={true}
          showReadMore={false}
          showFullBody={false}
          linkOverride={buildBackendPostPath(backendPost)}
          userUrlOverride={`/${data.author?.username}`}
          communityUrlOverride={backendPost.rubric_slug ? `/rubrics/${backendPost.rubric_slug}/posts` : undefined}
          subscribeUrl={backendPost.channel_url ?? data.author?.channel_url}
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
  <title>{title}</title>
  {#if description}
    <meta name="description" content={description} />
    <meta property="og:description" content={description} />
  {/if}
  <meta property="og:title" content={title} />
  <meta property="og:type" content="profile" />
  <meta property="og:url" content={canonicalUrl} />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
