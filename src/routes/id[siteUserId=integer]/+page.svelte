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
  import {
    deleteUserPost,
    fetchUserPosts,
    refreshSiteUser,
    siteToken,
    siteUser,
    type SiteUserPost,
  } from '$lib/siteAuth'
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
  let ownerPostsLoading = false
  let ownerPostsLoaded = false
  let ownerPostsError = ''
  let ownerPosts: SiteUserPost[] = []
  let deletingDraftId: number | null = null
  let profileTab: 'posts' | 'drafts' = 'posts'
  let lastOwnerProfileId: number | null = null
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
  $: isOwnProfile = Boolean(profile?.id && $siteUser?.id && profile.id === $siteUser.id)
  $: ownerDrafts = ownerPosts.filter((item) => item.is_draft)
  $: currentProfileId = profile?.id ?? null
  $: if (currentProfileId !== lastOwnerProfileId) {
    lastOwnerProfileId = currentProfileId
    ownerPostsLoading = false
    ownerPostsLoaded = false
    ownerPostsError = ''
    ownerPosts = []
    profileTab = 'posts'
  }

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
    if (profileTab !== 'posts' || loadingMore || !hasMore) return
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
    if ($siteToken) {
      void refreshSiteUser().catch(() => {})
    }
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

  const loadOwnerPosts = async () => {
    if (ownerPostsLoading || ownerPostsLoaded || !isOwnProfile) return
    ownerPostsLoading = true
    ownerPostsError = ''
    try {
      let offset = 0
      let total = 0
      const collected: SiteUserPost[] = []
      do {
        const payload = await fetchUserPosts(50, offset)
        const nextItems = payload.posts ?? []
        total = Number(payload.total ?? 0)
        if (!nextItems.length) break
        collected.push(...nextItems)
        offset += nextItems.length
      } while (collected.length < total)
      ownerPosts = collected
      ownerPostsLoaded = true
    } catch (error) {
      ownerPostsError = (error as Error)?.message ?? 'Не удалось загрузить черновики'
    } finally {
      ownerPostsLoading = false
    }
  }

  const copyDraftShareLink = async (draft: SiteUserPost) => {
    const token = draft.draft_share_token
    if (!token) return
    const url = `${$page.url.origin}/drafts/${encodeURIComponent(token)}`
    try {
      await navigator.clipboard.writeText(url)
    } catch (error) {
      console.error('Failed to copy draft share link:', error)
    }
  }

  const removeDraft = async (draft: SiteUserPost) => {
    if (deletingDraftId === draft.id) return
    const shouldDelete = confirm('Удалить черновик?')
    if (!shouldDelete) return
    deletingDraftId = draft.id
    ownerPostsError = ''
    try {
      await deleteUserPost(draft.id)
      ownerPosts = ownerPosts.filter((item) => item.id !== draft.id)
    } catch (error) {
      ownerPostsError = (error as Error)?.message ?? 'Не удалось удалить черновик'
    } finally {
      deletingDraftId = null
    }
  }

  $: if (isOwnProfile && $siteToken && !ownerPostsLoaded && !ownerPostsLoading) {
    void loadOwnerPosts()
  }
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
    <div class="flex flex-wrap items-center gap-2">
      <button
        type="button"
        class={`rounded-full px-4 py-2 text-sm transition-colors ${
          profileTab === 'posts'
            ? 'bg-slate-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
            : 'bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-zinc-300'
        }`}
        on:click={() => (profileTab = 'posts')}
      >
        Посты
      </button>
      {#if isOwnProfile}
        <button
          type="button"
          class={`rounded-full px-4 py-2 text-sm transition-colors ${
            profileTab === 'drafts'
              ? 'bg-slate-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
              : 'bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-zinc-300'
          }`}
          on:click={() => (profileTab = 'drafts')}
        >
          Черновики
        </button>
      {/if}
    </div>
    {#if profileTab === 'posts' && visiblePosts.length}
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
            subscribeUrl={backendPost.channel_url ?? backendPost.author?.channel_url}
            subscribeLabel="Подписаться"
          />
        {/each}
      </div>
      {#if loadingMore}
        <div class="text-sm text-slate-500">Загрузка...</div>
      {/if}
    {:else if profileTab === 'posts'}
      <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 text-sm text-slate-500 dark:text-zinc-400">
        Пока нет публикаций.
      </div>
    {:else if ownerPostsLoading}
      <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 text-sm text-slate-500 dark:text-zinc-400">
        Загружаем черновики...
      </div>
    {:else if ownerPostsError}
      <div class="rounded-2xl border border-red-200 dark:border-red-900/40 bg-white/95 dark:bg-zinc-900/85 p-4 text-sm text-red-600 dark:text-red-300">
        {ownerPostsError}
      </div>
    {:else if ownerDrafts.length}
      <div class="grid gap-3">
        {#each ownerDrafts as draft (draft.id)}
          <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4">
            <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div class="min-w-0">
                <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100 break-words">
                  {draft.title || 'Без заголовка'}
                </div>
                <div class="mt-1 text-sm text-slate-500 dark:text-zinc-400">
                  {#if draft.rubric}
                    <span>{draft.rubric}</span>
                    <span> · </span>
                  {/if}
                  <span>
                    Обновлён {new Intl.DateTimeFormat('ru-RU', {
                      day: '2-digit',
                      month: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit',
                    }).format(new Date(draft.updated_at || draft.created_at))}
                  </span>
                </div>
              </div>
              <div class="flex flex-wrap gap-2">
                <button
                  type="button"
                  class="inline-flex h-10 w-10 items-center justify-center rounded-full border border-red-200 bg-red-50 text-red-600 transition-colors hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300 dark:hover:bg-red-900/50"
                  aria-label="Удалить черновик"
                  title="Удалить черновик"
                  on:click={() => removeDraft(draft)}
                  disabled={deletingDraftId === draft.id}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M3 6h18" />
                    <path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
                    <path d="M19 6l-1 14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1L5 6" />
                    <path d="M10 11v6" />
                    <path d="M14 11v6" />
                  </svg>
                </button>
                {#if draft.draft_share_token}
                  <button
                    type="button"
                    class="rounded-full bg-slate-100 px-4 py-2 text-sm text-slate-700 dark:bg-zinc-800 dark:text-zinc-300"
                    on:click={() => copyDraftShareLink(draft)}
                  >
                    Скопировать ссылку
                  </button>
                {/if}
              </div>
            </div>
          </div>
        {/each}
      </div>
    {:else}
      <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 text-sm text-slate-500 dark:text-zinc-400">
        Пока нет черновиков.
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
