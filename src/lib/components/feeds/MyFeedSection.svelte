<script lang="ts">
  import { browser } from '$app/environment'
  import {
    buildTopComunsUrl,
    type BackendPost,
    type BackendTopComun,
  } from '$lib/api/backend'
  import FeedPostsList from '$lib/components/feeds/FeedPostsList.svelte'
  import { siteUser } from '$lib/siteAuth'
  import {
    feedSettingsHydrated,
    feedSettingsHydrationState,
    subscribeToComunBySlug,
    userSettings,
  } from '$lib/settings'
  import { Button } from 'mono-svelte'
  import { cachedJson } from '$lib/api/publicCache'

  export let posts: BackendPost[] = []
  export let loadingMore = false

  let topComuns: BackendTopComun[] = []
  let recommendedComuns: BackendTopComun[] = []
  let recommendedComunsLoading = false
  let recommendedComunsLoaded = false
  let recommendedComunsError = ''
  let filteredPosts: BackendPost[] = []
  let hiddenAuthorKeys = new Set<string>()

  const normalizeSlug = (value: string | null | undefined) =>
    String(value ?? '').trim().toLowerCase()

  const loadRecommendedComuns = async () => {
    if (!browser || recommendedComunsLoading || recommendedComunsLoaded) return
    recommendedComunsLoading = true
    recommendedComunsError = ''
    try {
      const payload = await cachedJson<{ comuns?: BackendTopComun[] }>(
        'public:top-comuns:50',
        buildTopComunsUrl({ limit: 50 }),
        { ttlMs: 21_600_000 }
      )
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

  $: selectedMyFeedComuns = $userSettings.myFeedComuns ?? []
  $: selectedMyFeedAuthors = $userSettings.myFeedAuthors ?? []
  $: selectedComunSlugSet = new Set(selectedMyFeedComuns.map(normalizeSlug))
  $: myFeedHasBaseSettings = selectedMyFeedComuns.length > 0 || selectedMyFeedAuthors.length > 0
  $: hiddenAuthorKeys = new Set(
    ($userSettings.hiddenAuthors ?? []).map((value) => value.toLowerCase())
  )
  $: filteredPosts = posts.filter(isAuthorVisible)
  $: recommendedComuns = topComuns
    .filter((comun) => !selectedComunSlugSet.has(normalizeSlug(comun.slug)))
    .slice(0, 3)
  $: shouldShowRecommendations =
    !!$siteUser &&
    $feedSettingsHydrated &&
    !loadingMore &&
    filteredPosts.length === 0

  $: if (shouldShowRecommendations && !recommendedComunsLoaded) {
    void loadRecommendedComuns()
  }

  $: if (!$siteUser) {
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
              Подпишитесь на сообщества или авторов, чтобы видеть их публикации здесь.
            </div>
          </div>
          {#if recommendedComunsLoading}
            <div class="text-sm text-slate-500 dark:text-zinc-400">Загружаем сообщества...</div>
          {:else if recommendedComunsError}
            <div class="text-sm text-rose-600 dark:text-rose-300">{recommendedComunsError}</div>
          {:else if recommendedComuns.length}
            <div class="flex flex-col gap-2">
              <div class="text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-zinc-500">
                Рекомендуемые сообщества
              </div>
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
            </div>
          {:else}
            <a href="/comuns" class="inline-flex text-sm text-blue-600 hover:underline dark:text-blue-400">
              Смотреть все сообщества
            </a>
          {/if}
        </div>
      </div>
    {/if}

    {#if $feedSettingsHydrated && $feedSettingsHydrationState !== 'error' && myFeedHasBaseSettings}
      {#if filteredPosts.length}
        <FeedPostsList posts={filteredPosts} {loadingMore} />
      {:else if loadingMore}
        <div class="text-base text-slate-500 dark:text-zinc-400">Загружаем публикации...</div>
      {:else if shouldShowRecommendations}
        <div class="rounded-2xl border border-slate-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
          <div class="flex flex-col gap-4">
            <div class="flex flex-col gap-2">
              <div class="text-base text-slate-700 dark:text-zinc-200">
                Пока нет постов в выбранных подписках.
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
              <div class="flex flex-col gap-2">
                <div class="text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-zinc-500">
                  Рекомендуемые сообщества
                </div>
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
