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
  import { t } from '$lib/translations'

  export let posts: BackendPost[] = []
  export let loadingMore = false

  const defaultRecommendedComunSlugs = [
    'Music',
    'after_the_credits',
    'wherefilmed',
    'nintendo-switch',
    'homm-7-olden-era',
    'entertainment',
  ]

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
      {$t('site.sidebar.myFeedSection.title')}
    </h1>
  </div>

  {#if !$siteUser}
    <RecommendedComunsPanel
      selectedSlugs={selectedMyFeedComuns}
      recommendedSlugs={defaultRecommendedComunSlugs}
      title={$t('site.sidebar.myFeedSection.setupTitle')}
      description={$t('site.sidebar.myFeedSection.setupDescription')}
    />
  {:else}
    {#if !$feedSettingsHydrated && $feedSettingsHydrationState !== 'error'}
      <div class="text-base text-slate-500 dark:text-zinc-400">{$t('site.sidebar.myFeedSection.loadingSettings')}</div>
    {:else if $feedSettingsHydrationState === 'error'}
      <div class="text-base text-rose-600 dark:text-rose-300">
        {$t('site.sidebar.myFeedSection.settingsError')}
      </div>
    {:else if !myFeedHasBaseSettings}
      <RecommendedComunsPanel
        selectedSlugs={selectedMyFeedComuns}
        recommendedSlugs={defaultRecommendedComunSlugs}
        title={$t('site.sidebar.myFeedSection.setupTitle')}
        description={$t('site.sidebar.myFeedSection.setupDescription')}
      />
    {/if}

    {#if $feedSettingsHydrated && $feedSettingsHydrationState !== 'error' && myFeedHasBaseSettings}
      {#if filteredPosts.length}
        <FeedPostsList posts={filteredPosts} {loadingMore} />
      {:else if loadingMore}
        <div class="text-base text-slate-500 dark:text-zinc-400">{$t('site.sidebar.myFeedSection.loadingPosts')}</div>
      {:else if shouldShowRecommendations}
        <RecommendedComunsPanel
          selectedSlugs={selectedMyFeedComuns}
          recommendedSlugs={defaultRecommendedComunSlugs}
          title={$t('site.sidebar.myFeedSection.emptyTitle')}
          description={$t('site.sidebar.myFeedSection.emptyDescription')}
        />
      {:else}
        <div class="text-base text-slate-500">{$t('site.sidebar.myFeedSection.noPublications')}</div>
      {/if}
    {/if}
  {/if}
</div>
