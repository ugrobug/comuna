<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import {
    buildThematicFeedsListUrl,
    buildTopComunsUrl,
    type BackendPost,
    type BackendThematicFeed,
    type BackendTopComun,
  } from '$lib/api/backend'
  import FeedPostsList from '$lib/components/feeds/FeedPostsList.svelte'
  import {
    buildMyFeedSettingsFromFolderPreset,
    hasMyFeedCustomizations,
  } from '$lib/feeds/myFeed'
  import { siteUser } from '$lib/siteAuth'
  import {
    feedSettingsHydrated,
    feedSettingsHydrationState,
    subscribeToComunBySlug,
    userSettings,
  } from '$lib/settings'
  import { Button } from 'mono-svelte'

  export let posts: BackendPost[] = []
  export let loadingMore = false

  let myFeedSuggestedFolders: BackendThematicFeed[] = []
  let myFeedSuggestedFoldersLoading = false
  let myFeedSuggestedFoldersLoaded = false
  let myFeedSuggestedFoldersError = ''
  let topComuns: BackendTopComun[] = []
  let recommendedComuns: BackendTopComun[] = []
  let recommendedComunsLoading = false
  let recommendedComunsLoaded = false
  let recommendedComunsError = ''
  let filteredPosts: BackendPost[] = []
  let hiddenAuthorKeys = new Set<string>()

  const normalizeSlug = (value: string | null | undefined) =>
    String(value ?? '').trim().toLowerCase()

  const loadMyFeedSuggestedFolders = async () => {
    if (!browser || myFeedSuggestedFoldersLoading) return
    myFeedSuggestedFoldersLoading = true
    myFeedSuggestedFoldersError = ''
    try {
      const response = await fetch(buildThematicFeedsListUrl())
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось загрузить список папок')
      }
      myFeedSuggestedFolders = payload.folders ?? payload.feeds ?? []
      myFeedSuggestedFoldersLoaded = true
    } catch (error) {
      myFeedSuggestedFoldersError =
        error instanceof Error ? error.message : 'Ошибка загрузки папок'
      myFeedSuggestedFoldersLoaded = true
    } finally {
      myFeedSuggestedFoldersLoading = false
    }
  }

  const loadRecommendedComuns = async () => {
    if (!browser || recommendedComunsLoading || recommendedComunsLoaded) return
    recommendedComunsLoading = true
    recommendedComunsError = ''
    try {
      const response = await fetch(buildTopComunsUrl({ limit: 'all' }))
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось загрузить рекомендации')
      }
      topComuns = payload.comuns ?? []
      recommendedComunsLoaded = true
    } catch (error) {
      recommendedComunsError =
        error instanceof Error ? error.message : 'Ошибка загрузки рекомендаций'
      recommendedComunsLoaded = true
    } finally {
      recommendedComunsLoading = false
    }
  }

  const applyFolderPresetToMyFeed = async (folderPreset: BackendThematicFeed | null) => {
    if (!folderPreset) return
    if (!$siteUser) {
      const next = encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)
      goto(`/account?next=${next}`)
      return
    }
    if (browser && hasMyFeedCustomizations($userSettings)) {
      const confirmed = window.confirm(
        'У вас уже настроена "Моя лента". Нажатие на кнопку заменит текущие настройки настройками папки. После этого вы сможете дополнительно настроить свою ленту. Продолжить?'
      )
      if (!confirmed) return
    }
    $userSettings = buildMyFeedSettingsFromFolderPreset($userSettings, folderPreset)
    goto('/?feed=mine')
  }

  const subscribeToComun = (comun: BackendTopComun) => {
    const slug = normalizeSlug(comun.slug)
    if (!slug) return
    subscribeToComunBySlug(comun.slug)
  }

  const authorKey = (backendPost: { author?: { username?: string } }) =>
    (backendPost.author?.username ?? '').trim().toLowerCase()

  const isAuthorVisible = (backendPost: { author?: { username?: string } }) => {
    const key = authorKey(backendPost)
    if (!key) return true
    return !hiddenAuthorKeys.has(key)
  }

  $: selectedRubrics = $userSettings.myFeedRubrics ?? []
  $: selectedAuthors = $userSettings.myFeedAuthors ?? []
  $: selectedMyFeedTags = $userSettings.myFeedTags ?? []
  $: selectedMyFeedComuns = $userSettings.myFeedComuns ?? []
  $: selectedComunSlugSet = new Set(selectedMyFeedComuns.map(normalizeSlug))
  $: myFeedHasBaseSettings =
    selectedRubrics.length > 0 ||
    selectedAuthors.length > 0 ||
    selectedMyFeedTags.length > 0 ||
    selectedMyFeedComuns.length > 0
  $: hiddenAuthorKeys = new Set(
    ($userSettings.hiddenAuthors ?? []).map((value) => value.toLowerCase())
  )
  $: filteredPosts = posts.filter(isAuthorVisible)
  $: recommendedComuns = topComuns
    .filter((comun) => !selectedComunSlugSet.has(normalizeSlug(comun.slug)))
    .slice(0, 3)
  $: shouldShowEmptyRecommendations =
    !!$siteUser &&
    $feedSettingsHydrated &&
    myFeedHasBaseSettings &&
    !loadingMore &&
    filteredPosts.length === 0

  $: if (
    browser &&
    !!$siteUser &&
    $feedSettingsHydrated &&
    !myFeedHasBaseSettings &&
    !myFeedSuggestedFoldersLoaded
  ) {
    void loadMyFeedSuggestedFolders()
  }

  $: if (shouldShowEmptyRecommendations && !recommendedComunsLoaded) {
    void loadRecommendedComuns()
  }

  $: if (!$siteUser) {
    myFeedSuggestedFolders = []
    myFeedSuggestedFoldersLoaded = false
    myFeedSuggestedFoldersLoading = false
    myFeedSuggestedFoldersError = ''
    topComuns = []
    recommendedComunsLoaded = false
    recommendedComunsLoading = false
    recommendedComunsError = ''
  }
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
      <div class="rounded-2xl border border-slate-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex flex-col gap-4">
          <div class="flex flex-col gap-2">
            <div class="text-sm text-slate-700 dark:text-zinc-200">
              Ваша лента пока не настроена.
            </div>
            <div class="text-sm text-slate-500 dark:text-zinc-400">
              Выберите готовую папку или добавьте сообщества в настройках сайта.
            </div>
          </div>
          <a href="/settings" class="inline-flex items-center text-sm text-blue-600 hover:underline dark:text-blue-400">
            Открыть настройки сайта
          </a>
          <div class="flex flex-col gap-3">
            <div class="text-sm font-medium text-slate-800 dark:text-zinc-200">
              Готовые папки
            </div>
            {#if myFeedSuggestedFoldersLoading}
              <div class="text-sm text-slate-500 dark:text-zinc-400">Загружаем папки...</div>
            {:else if myFeedSuggestedFoldersError}
              <div class="text-sm text-rose-600 dark:text-rose-300">{myFeedSuggestedFoldersError}</div>
            {:else if myFeedSuggestedFolders.length}
              <div class="grid gap-2 md:grid-cols-2">
                {#each myFeedSuggestedFolders as folder}
                  <div class="rounded-xl border border-slate-200 p-3 dark:border-zinc-800">
                    <div class="flex flex-col gap-2 min-w-0">
                      <div class="min-w-0">
                        <div class="truncate text-sm font-medium text-slate-900 dark:text-zinc-100">
                          {folder.name}
                        </div>
                        {#if folder.description}
                          <div class="line-clamp-2 text-xs text-slate-500 dark:text-zinc-400">
                            {folder.description}
                          </div>
                        {/if}
                      </div>
                      <div class="text-xs text-slate-500 dark:text-zinc-400">
                        {folder.authors_count ?? 0} авторов · {folder.tags_count ?? 0} тегов · {folder.blocked_tags_count ?? 0} искл. тегов
                      </div>
                      <div class="flex flex-wrap gap-2">
                        <Button on:click={() => applyFolderPresetToMyFeed(folder)}>
                          Сделать моей лентой
                        </Button>
                        <a
                          href={`/?feed=thematic&theme=${encodeURIComponent(folder.slug)}`}
                          class="inline-flex items-center text-sm text-blue-600 hover:underline dark:text-blue-400"
                        >
                          Открыть папку
                        </a>
                      </div>
                    </div>
                  </div>
                {/each}
              </div>
            {:else}
              <div class="text-sm text-slate-500 dark:text-zinc-400">
                Пока нет готовых папок. Можно выбрать сообщества в настройках сайта.
              </div>
            {/if}
          </div>
        </div>
      </div>
    {/if}

    {#if $feedSettingsHydrated && $feedSettingsHydrationState !== 'error' && myFeedHasBaseSettings}
      {#if filteredPosts.length}
        <FeedPostsList posts={filteredPosts} {loadingMore} />
      {:else if loadingMore}
        <div class="text-base text-slate-500 dark:text-zinc-400">Загружаем публикации...</div>
      {:else if shouldShowEmptyRecommendations}
        <div class="rounded-2xl border border-slate-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
          <div class="flex flex-col gap-4">
            <div class="flex flex-col gap-2">
              <div class="text-base text-slate-700 dark:text-zinc-200">
                Пока нет постов в выбранных сообществах.
              </div>
              <div class="text-sm text-slate-500 dark:text-zinc-400">
                Подпишитесь на новые сообщества, чтобы видеть больше постов.
              </div>
            </div>
            {#if recommendedComunsLoading}
              <div class="text-sm text-slate-500 dark:text-zinc-400">Загружаем сообщества...</div>
            {:else if recommendedComunsError}
              <div class="text-sm text-rose-600 dark:text-rose-300">{recommendedComunsError}</div>
            {:else if recommendedComuns.length}
              <div class="grid gap-2 md:grid-cols-3">
                {#each recommendedComuns as comun}
                  <div class="flex min-w-0 flex-col gap-3 rounded-xl border border-slate-200 p-3 dark:border-zinc-800">
                    <div class="min-w-0">
                      <a
                        href={`/comuns/${encodeURIComponent(comun.slug)}`}
                        class="block truncate text-sm font-medium text-slate-900 hover:text-blue-600 dark:text-zinc-100 dark:hover:text-blue-400"
                      >
                        {comun.name}
                      </a>
                      <div class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
                        Рейтинг {comun.rating ?? comun.score ?? 0} · {comun.posts_count ?? 0} постов
                      </div>
                    </div>
                    <Button color="ghost" on:click={() => subscribeToComun(comun)}>
                      Подписаться
                    </Button>
                  </div>
                {/each}
              </div>
            {:else}
              <a href="/comuns" class="inline-flex text-sm text-blue-600 hover:underline dark:text-blue-400">
                Смотреть все сообщества
              </a>
            {/if}
          </div>
        </div>
      {:else}
        <div class="text-base text-slate-500">Пока нет публикаций.</div>
      {/if}
    {/if}
  {/if}
</div>
