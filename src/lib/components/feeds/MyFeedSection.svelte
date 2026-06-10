<script lang="ts">
  import type { BackendPost } from '$lib/api/backend'
  import FeedPostsList from '$lib/components/feeds/FeedPostsList.svelte'
  import RecommendedComunsPanel from '$lib/components/feeds/RecommendedComunsPanel.svelte'
  import { siteUser } from '$lib/siteAuth'
  import {
    feedSettingsHydrated,
    feedSettingsHydrationState,
    userSettings,
  } from '$lib/settings'

  export let posts: BackendPost[] = []
  export let loadingMore = false

  let filteredPosts: BackendPost[] = []
  let hiddenAuthorKeys = new Set<string>()

  const authorKey = (backendPost: { author?: { username?: string } }) =>
    (backendPost.author?.username ?? '').trim().toLowerCase()

  const isAuthorVisible = (backendPost: { author?: { username?: string } }) => {
    const key = authorKey(backendPost)
    if (!key) return true
    return !hiddenAuthorKeys.has(key)
  }

  $: selectedMyFeedComuns = $userSettings.myFeedComuns ?? []
  $: selectedMyFeedAuthors = $userSettings.myFeedAuthors ?? []
  $: myFeedHasBaseSettings = selectedMyFeedComuns.length > 0 || selectedMyFeedAuthors.length > 0
  $: hiddenAuthorKeys = new Set(
    ($userSettings.hiddenAuthors ?? []).map((value) => value.toLowerCase())
  )
  $: filteredPosts = posts.filter(isAuthorVisible)
  $: shouldShowRecommendations =
    !!$siteUser &&
    $feedSettingsHydrated &&
    !loadingMore &&
    filteredPosts.length === 0
</script>

<div class="flex flex-col gap-4">
  <div class="flex items-center justify-between gap-3">
    <h1 class="text-2xl font-semibold text-slate-900 dark:text-zinc-100">
      Моя лента
    </h1>
  </div>

  {#if !$siteUser}
    <div class="text-base text-slate-500">
      После регистрации вы получите доступ к персонализируемой ленте и сможете видеть только интересные вам посты.
    </div>
  {:else}
    {#if !$feedSettingsHydrated && $feedSettingsHydrationState !== 'error'}
      <div class="text-base text-slate-500 dark:text-zinc-400">Загружаем мою ленту...</div>
    {:else if $feedSettingsHydrationState === 'error'}
      <div class="text-base text-rose-600 dark:text-rose-300">
        Не удалось загрузить настройки ленты. Обновите страницу или попробуйте позже.
      </div>
    {:else if !myFeedHasBaseSettings}
      <RecommendedComunsPanel
        selectedSlugs={selectedMyFeedComuns}
        title="Ваша лента пока не настроена"
        description="Подпишитесь на сообщества или авторов, чтобы видеть их публикации здесь."
      />
    {/if}

    {#if $feedSettingsHydrated && $feedSettingsHydrationState !== 'error' && myFeedHasBaseSettings}
      {#if filteredPosts.length}
        <FeedPostsList posts={filteredPosts} {loadingMore} />
      {:else if loadingMore}
        <div class="text-base text-slate-500 dark:text-zinc-400">Загружаем публикации...</div>
      {:else if shouldShowRecommendations}
        <RecommendedComunsPanel
          selectedSlugs={selectedMyFeedComuns}
          title="Пока нет постов в выбранных подписках"
          description="Подпишитесь на новые сообщества, чтобы видеть больше постов."
        />
      {:else}
        <div class="text-base text-slate-500">Пока нет публикаций.</div>
      {/if}
    {/if}
  {/if}
</div>
