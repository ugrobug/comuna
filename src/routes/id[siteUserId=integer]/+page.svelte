<script lang="ts">
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import { onDestroy, onMount } from 'svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { feedKeyboardShortcuts } from '$lib/actions/feedKeyboardShortcuts'
  import {
    backendPostToPostView,
    buildBackendPostPath,
    buildPublicUserProfileUrl,
    type BackendPost,
    type BackendPublicSiteUser,
    type BackendPublicSiteUserAuthor,
    type BackendPublicSiteUserComun,
  } from '$lib/api/backend'
  import { env } from '$env/dynamic/public'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import { userSettings } from '$lib/settings'

  export let data

  const pageSize = data.pageSize ?? 10
  let profile: BackendPublicSiteUser | null = data.profile ?? null
  let authors: BackendPublicSiteUserAuthor[] = data.authors ?? []
  let comuns: BackendPublicSiteUserComun[] = data.comuns ?? []
  let posts: BackendPost[] = data.posts ?? []
  let totalPosts = data.totalPosts ?? 0
  let hasMore = posts.length >= pageSize && posts.length < totalPosts
  let loadingMore = false
  let lastPostsRef = data.posts
  let lastProfileRef = data.profile
  let lastAuthorsRef = data.authors
  let lastComunsRef = data.comuns
  const scrollThreshold = 400
  let scrollRaf: number | null = null

  $: if (data?.posts && data.posts !== lastPostsRef) {
    lastPostsRef = data.posts
    posts = data.posts ?? []
    totalPosts = data.totalPosts ?? totalPosts
    hasMore = posts.length >= pageSize && posts.length < totalPosts
    loadingMore = false
  }
  $: if (data?.profile && data.profile !== lastProfileRef) {
    lastProfileRef = data.profile
    profile = data.profile ?? null
  }
  $: if (data?.authors && data.authors !== lastAuthorsRef) {
    lastAuthorsRef = data.authors
    authors = data.authors ?? []
  }
  $: if (data?.comuns && data.comuns !== lastComunsRef) {
    lastComunsRef = data.comuns
    comuns = data.comuns ?? []
  }

  $: hiddenAuthorKeys = new Set(
    ($userSettings.hiddenAuthors ?? []).map((value) => value.toLowerCase())
  )
  const authorKey = (backendPost: { author?: { username?: string } }) =>
    (backendPost.author?.username ?? '').trim().toLowerCase()
  const isAuthorVisible = (backendPost: { author?: { username?: string } }) => {
    const key = authorKey(backendPost)
    if (!key) return true
    return !hiddenAuthorKeys.has(key)
  }
  $: visiblePosts = posts.filter(isAuthorVisible)

  const formatNumber = (value: number | undefined) => {
    if (!value && value !== 0) return '—'
    return value.toLocaleString('ru-RU')
  }

  const userDisplayName = (user: BackendPublicSiteUser | null) => {
    if (!user) return 'Пользователь'
    const displayName = (user.display_name || '').trim()
    if (displayName) return displayName
    const fullName = [user.first_name, user.last_name].filter(Boolean).join(' ').trim()
    return fullName || `@${user.username}`
  }

  const initials = (value?: string | null) =>
    (value || '?').trim().slice(0, 1).toUpperCase() || '?'

  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Comuna'
  $: profilePath = profile?.id ? `/id${profile.id}` : $page.url.pathname
  $: title = profile ? `${userDisplayName(profile)} — ${siteTitle}` : siteTitle
  $: description = profile
    ? `Профиль пользователя @${profile.username} на ${siteTitle}: посты и комунны.`
    : `Профиль пользователя на ${siteTitle}.`
  $: canonicalUrl = new URL(
    profilePath,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()

  const buildPageUrl = (offset: number) => {
    const id = profile?.id ?? data.profile?.id
    if (!id) return ''
    return buildPublicUserProfileUrl(id, { limit: pageSize, offset })
  }

  const loadMore = async () => {
    if (loadingMore || !hasMore) return
    const url = buildPageUrl(posts.length)
    if (!url) return
    loadingMore = true
    try {
      const token = $siteToken
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined
      const response = await fetch(url, { headers })
      if (!response.ok) {
        hasMore = false
        return
      }
      const payload = await response.json()
      if (payload?.user) profile = payload.user
      if (Array.isArray(payload?.authors)) authors = payload.authors
      if (Array.isArray(payload?.comuns)) comuns = payload.comuns
      if (typeof payload?.total_posts === 'number') totalPosts = payload.total_posts
      const nextPosts = (payload?.posts ?? []) as BackendPost[]
      if (nextPosts.length) {
        posts = [...posts, ...nextPosts]
      }
      hasMore = nextPosts.length >= pageSize && posts.length < totalPosts
    } catch (error) {
      console.error('Failed to load more profile posts:', error)
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
</script>

<div class="flex flex-col gap-6 max-w-5xl w-full">
  <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-5 sm:p-6">
    <div class="flex flex-col sm:flex-row gap-5 items-start">
      <div class="w-20 h-20 rounded-full overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
        {#if profile?.avatar_url}
          <img src={profile.avatar_url} alt={userDisplayName(profile)} class="w-full h-full object-cover" />
        {:else}
          <div class="w-full h-full grid place-items-center text-xl font-bold text-slate-500 dark:text-zinc-400">
            {initials(userDisplayName(profile))}
          </div>
        {/if}
      </div>
      <div class="min-w-0 flex-1 flex flex-col gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="text-2xl font-semibold text-slate-900 dark:text-zinc-100 break-words">
            {userDisplayName(profile)}
          </h1>
          {#if profile?.is_staff}
            <span class="px-2 py-1 rounded-full text-xs bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
              admin
            </span>
          {/if}
        </div>
        {#if profile?.username}
          <div class="text-sm text-slate-500 dark:text-zinc-400">@{profile.username}</div>
        {/if}
        <div class="flex flex-wrap gap-2 text-sm">
          <span class="px-3 py-1.5 rounded-full bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300">
            {formatNumber(profile?.posts_count)} постов
          </span>
          <span class="px-3 py-1.5 rounded-full bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300">
            {formatNumber(profile?.comuns_count)} коммун
          </span>
          {#if profile?.authors_count}
            <span class="px-3 py-1.5 rounded-full bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300">
              {formatNumber(profile?.authors_count)} каналов
            </span>
          {/if}
        </div>
      </div>
    </div>
  </section>

  <section class="flex flex-col gap-3">
    <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Каналы</div>
    {#if authors.length}
      <div class="grid gap-3 sm:grid-cols-2">
        {#each authors as author}
          <a
            href={`/${author.username}`}
            class="group rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 hover:border-slate-300 dark:hover:border-zinc-700 transition-colors"
          >
            <div class="flex items-start gap-3">
              <div class="w-12 h-12 rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
                {#if author.avatar_url}
                  <img src={author.avatar_url} alt={author.title || author.username} class="w-full h-full object-cover" />
                {:else}
                  <div class="w-full h-full grid place-items-center text-sm font-semibold text-slate-500 dark:text-zinc-400">
                    {initials(author.title || author.username)}
                  </div>
                {/if}
              </div>
              <div class="min-w-0 flex-1">
                <div class="font-semibold text-slate-900 dark:text-zinc-100 truncate">
                  {author.title || `@${author.username}`}
                </div>
                <div class="mt-0.5 text-xs text-slate-500 dark:text-zinc-400 truncate">
                  @{author.username}
                </div>
                {#if author.rubric}
                  <div class="mt-1 text-xs text-slate-500 dark:text-zinc-400 truncate">
                    Рубрика: {author.rubric}
                  </div>
                {/if}
                {#if author.description}
                  <div class="mt-1 text-sm text-slate-600 dark:text-zinc-300 line-clamp-2">
                    {author.description}
                  </div>
                {/if}
              </div>
            </div>
          </a>
        {/each}
      </div>
    {:else}
      <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 text-sm text-slate-500 dark:text-zinc-400">
        Пока нет привязанных каналов.
      </div>
    {/if}
  </section>

  <section class="flex flex-col gap-3">
    <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Комуны</div>
    {#if comuns.length}
      <div class="grid gap-3 sm:grid-cols-2">
        {#each comuns as comun}
          <a
            href={`/comuns/${comun.slug}/`}
            class="group rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 hover:border-slate-300 dark:hover:border-zinc-700 transition-colors"
          >
            <div class="flex items-start gap-3">
              <div class="w-12 h-12 rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
                {#if comun.logo_url}
                  <img src={comun.logo_url} alt={comun.name} class="w-full h-full object-cover" />
                {:else}
                  <div class="w-full h-full grid place-items-center text-sm font-semibold text-slate-500 dark:text-zinc-400">
                    {initials(comun.name)}
                  </div>
                {/if}
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <div class="font-semibold text-slate-900 dark:text-zinc-100 truncate">{comun.name}</div>
                  {#if comun.role}
                    <span class="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-300">
                      {comun.role === 'creator' ? 'создатель' : 'модератор'}
                    </span>
                  {/if}
                </div>
                {#if comun.product_tag?.name}
                  <div class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
                    #{comun.product_tag.name}
                  </div>
                {/if}
                {#if comun.product_description}
                  <div class="mt-1 text-sm text-slate-600 dark:text-zinc-300 line-clamp-2">
                    {comun.product_description}
                  </div>
                {/if}
              </div>
            </div>
          </a>
        {/each}
      </div>
    {:else}
      <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 text-sm text-slate-500 dark:text-zinc-400">
        Пока нет коммун.
      </div>
    {/if}
  </section>

  <section class="flex flex-col gap-3">
    <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Посты</div>
    {#if visiblePosts.length}
      <div class="flex flex-col gap-6" use:feedKeyboardShortcuts>
        {#each visiblePosts as backendPost (backendPost.id)}
          <Post
            post={backendPostToPostView(backendPost)}
            class="feed-shortcut-post rounded-2xl border border-slate-200/80 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 shadow-sm px-4 sm:px-5"
            view="cozy"
            actions={true}
            showReadMore={false}
            showFullBody={false}
            linkOverride={buildBackendPostPath(backendPost)}
            userUrlOverride={backendPost.author?.username ? `/${backendPost.author.username}` : undefined}
            communityUrlOverride={backendPost.rubric_slug ? `/rubrics/${backendPost.rubric_slug}/posts` : undefined}
            subscribeUrl={(backendPost.channel_url ?? backendPost.author?.channel_url) ?? undefined}
            subscribeLabel="Подписаться"
          />
        {/each}
      </div>
      {#if loadingMore}
        <div class="text-sm text-slate-500">Загрузка...</div>
      {/if}
    {:else}
      <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 text-sm text-slate-500 dark:text-zinc-400">
        Пока нет публикаций.
      </div>
    {/if}
  </section>
</div>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="profile" />
  <meta property="og:url" content={canonicalUrl} />
  {#if profile?.avatar_url}
    <meta property="og:image" content={profile.avatar_url} />
    <meta name="twitter:image" content={profile.avatar_url} />
    <meta name="twitter:card" content="summary_large_image" />
  {:else}
    <meta name="twitter:card" content="summary" />
  {/if}
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
