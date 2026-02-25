<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { onDestroy, onMount } from 'svelte'
  import { Button, Modal, toast } from 'mono-svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { feedKeyboardShortcuts } from '$lib/actions/feedKeyboardShortcuts'
  import {
    backendPostToPostView,
    buildBackendPostPath,
    buildComunPostCategoryUrl,
    buildComunPostsUrl,
    buildComunUrl,
    type BackendComun,
    type BackendComunCategory,
    type BackendPost,
    type BackendTag,
  } from '$lib/api/backend'
  import { siteToken, uploadSiteImage } from '$lib/siteAuth'
  import { env } from '$env/dynamic/public'
  import { userSettings } from '$lib/settings'

  export let data

  const pageSize = data.pageSize ?? 10
  let comun: BackendComun | null = data.comun ?? null
  let posts: BackendPost[] = data.posts ?? []
  let selectedCategorySlug = data.selectedCategory?.slug ?? data.initialCategorySlug ?? ''
  let hasMore = posts.length === pageSize
  let loadingMore = false
  let loadingCategory = false
  let lastPostsRef = data.posts
  let lastComunRef = data.comun
  const scrollThreshold = 400
  let scrollRaf: number | null = null
  let categorySavingPostIds = new Set<number>()

  let settingsOpen = false
  let settingsLoading = false
  let settingsSaving = false
  let settingsLogoUploading = false
  let settingsError = ''
  let settingsTagSearch = ''
  let settingsDraft: BackendComun | null = null
  let settingsLogoInput: HTMLInputElement | null = null
  let lastAuthRefreshToken: string | null = null
  let autoSettingsOpenHandled = false
  let wantsSettingsOpenFromUrl = false
  let settingsCategoryOptions: BackendComunCategory[] = []
  type ComunTagOption = BackendTag & { id: number }
  let settingsTagOptions: ComunTagOption[] = []

  $: if (data?.posts && data.posts !== lastPostsRef) {
    lastPostsRef = data.posts
    posts = data.posts ?? []
    hasMore = posts.length === pageSize
    loadingMore = false
  }
  $: if (data?.comun && data.comun !== lastComunRef) {
    lastComunRef = data.comun
    comun = data.comun ?? null
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

  const isModerator = () => Boolean(comun?.can_moderate && $siteToken)

  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Comuna'
  $: comunName = comun?.name || 'Комуна'
  $: welcomePostView = comun?.welcome_post ? backendPostToPostView(comun.welcome_post) : null
  $: title = `${comunName} — ${siteTitle}`
  $: description =
    comun?.product_description || `Посты и обсуждения продукта «${comunName}» на ${siteTitle}.`
  $: canonicalUrl = new URL(
    $page.url.pathname + (selectedCategorySlug ? `?category=${encodeURIComponent(selectedCategorySlug)}` : ''),
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()

  const cloneComun = (value: BackendComun | null): BackendComun | null =>
    value ? JSON.parse(JSON.stringify(value)) : null

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  const buildPostsUrl = (offset: number) => {
    if (!comun?.slug) return ''
    const url = new URL(buildComunPostsUrl(comun.slug, { categorySlug: selectedCategorySlug || undefined }))
    url.searchParams.set('limit', String(pageSize))
    url.searchParams.set('offset', String(offset))
    return url.toString()
  }

  const applyPostsPayload = (payload: any, reset = false) => {
    if (payload?.comun) {
      comun = payload.comun
    }
    const nextPosts = (payload?.posts ?? []) as BackendPost[]
    if (reset) {
      posts = nextPosts
    } else if (nextPosts.length) {
      posts = [...posts, ...nextPosts]
    }
    hasMore = nextPosts.length === pageSize
  }

  const loadPosts = async (reset = false) => {
    if (loadingMore || loadingCategory) return
    const url = buildPostsUrl(reset ? 0 : posts.length)
    if (!url) return
    if (reset) {
      loadingCategory = true
    } else {
      loadingMore = true
    }
    try {
      const response = await fetch(url, $siteToken ? { headers: { Authorization: `Bearer ${$siteToken}` } } : undefined)
      if (!response.ok) {
        throw new Error('Не удалось загрузить посты комуны')
      }
      const payload = await response.json()
      applyPostsPayload(payload, reset)
    } catch (error) {
      console.error(error)
      toast(error instanceof Error ? error.message : 'Ошибка загрузки')
    } finally {
      loadingMore = false
      loadingCategory = false
    }
  }

  const maybeLoadMore = () => {
    if (!browser || loadingMore || loadingCategory || !hasMore) return
    const viewportBottom = window.scrollY + window.innerHeight
    const pageHeight = document.documentElement.scrollHeight
    if (pageHeight - viewportBottom <= scrollThreshold) {
      void loadPosts(false)
    }
  }

  const onScroll = () => {
    if (scrollRaf !== null) return
    scrollRaf = window.requestAnimationFrame(() => {
      scrollRaf = null
      maybeLoadMore()
    })
  }

  const setCategoryFilter = async (slug: string) => {
    if (slug === selectedCategorySlug) return
    selectedCategorySlug = slug
    hasMore = true
    await goto(
      slug ? `${$page.url.pathname}?category=${encodeURIComponent(slug)}` : $page.url.pathname,
      { replaceState: true, noScroll: true, keepFocus: true }
    )
    await loadPosts(true)
    if (browser) window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const refreshComunManage = async () => {
    if (!comun?.slug || !$siteToken) return
    settingsLoading = true
    settingsError = ''
    try {
      const response = await fetch(buildComunUrl(comun.slug), {
        headers: { Authorization: `Bearer ${$siteToken}` },
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось загрузить настройки комуны')
      }
      if (payload?.comun) {
        comun = payload.comun
        settingsDraft = cloneComun(payload.comun)
        settingsCategoryOptions = payload.comun?.options?.categories ?? []
        settingsTagOptions = payload.comun?.options?.tags ?? []
      }
    } catch (error) {
      settingsError = error instanceof Error ? error.message : 'Ошибка загрузки'
    } finally {
      settingsLoading = false
    }
  }

  const openSettings = async () => {
    if (!$siteToken) {
      const next = `${$page.url.pathname}?settings=1`
      goto(`/account?next=${encodeURIComponent(next)}`)
      return
    }
    settingsTagSearch = ''
    settingsDraft = cloneComun(comun)
    await refreshComunManage()
    if (!comun?.can_moderate) {
      toast('Настройки доступны только модераторам комуны')
      return
    }
    settingsOpen = true
  }

  const toggleDraftCategory = (categoryId: number) => {
    if (!settingsDraft) return
    const current = new Set((settingsDraft.category_ids ?? settingsDraft.categories ?? []).map((item: any) =>
      typeof item === 'number' ? item : item?.id
    ).filter(Boolean))
    if (current.has(categoryId)) current.delete(categoryId)
    else current.add(categoryId)
    settingsDraft = { ...settingsDraft, category_ids: Array.from(current) as number[] }
  }

  const chooseDraftTag = (tag: ComunTagOption) => {
    if (!settingsDraft) return
    settingsDraft = {
      ...settingsDraft,
      product_tag_id: tag.id,
      product_tag: { id: tag.id, name: tag.name, lemma: tag.lemma ?? null },
    }
  }

  const clearDraftTag = () => {
    if (!settingsDraft) return
    settingsDraft = { ...settingsDraft, product_tag_id: null, product_tag: null }
  }

  $: normalizedTagSearch = settingsTagSearch.trim().toLowerCase()
  $: draftCategoryIdSet = new Set<number>(
    ((settingsDraft?.category_ids as number[] | undefined) ??
      (settingsDraft?.categories ?? []).map((item) => item.id)) as number[]
  )
  $: filteredTagOptions = (settingsTagOptions ?? []).filter((tag) => {
    if (!normalizedTagSearch) return true
    return [tag.name, tag.lemma ?? ''].some((value) => value.toLowerCase().includes(normalizedTagSearch))
  }).slice(0, 30)

  const saveSettings = async () => {
    if (!comun?.slug || !settingsDraft) return
    settingsSaving = true
    settingsError = ''
    try {
      const response = await fetch(buildComunUrl(comun.slug), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({
          website_url: settingsDraft.website_url ?? '',
          logo_url: settingsDraft.logo_url ?? '',
          product_description: settingsDraft.product_description ?? '',
          target_audience: settingsDraft.target_audience ?? '',
          product_tag_id: settingsDraft.product_tag_id ?? null,
          category_ids: settingsDraft.category_ids ?? (settingsDraft.categories ?? []).map((category) => category.id),
          welcome_post_ref: settingsDraft.welcome_post_ref ?? '',
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось сохранить настройки')
      }
      comun = payload.comun ?? comun
      settingsDraft = cloneComun(comun)
      toast('Настройки комуны сохранены')
      await loadPosts(true)
    } catch (error) {
      settingsError = error instanceof Error ? error.message : 'Ошибка сохранения'
    } finally {
      settingsSaving = false
    }
  }

  const pickSettingsLogo = () => {
    if (!isModerator()) return
    settingsLogoInput?.click()
  }

  const onSettingsLogoSelected = async (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    const file = input?.files?.[0]
    if (!file || !settingsDraft) return

    settingsLogoUploading = true
    try {
      const uploadedUrl = await uploadSiteImage(file)
      settingsDraft = { ...settingsDraft, logo_url: uploadedUrl }
      toast('Логотип загружен. Нажмите «Сохранить» для применения.')
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Не удалось загрузить логотип')
    } finally {
      settingsLogoUploading = false
      if (input) input.value = ''
    }
  }

  const setWelcomePost = async (postId: number) => {
    if (!comun?.slug || !isModerator()) return
    try {
      const response = await fetch(buildComunUrl(comun.slug), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ welcome_post_id: postId }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload?.error || 'Не удалось выбрать приветственный пост')
      comun = payload.comun ?? comun
      toast('Приветственный пост обновлен')
      await loadPosts(true)
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Ошибка обновления')
    }
  }

  const updatePostCategory = async (postId: number, categoryId: number | null) => {
    if (!comun?.slug || !isModerator()) return
    categorySavingPostIds = new Set([...categorySavingPostIds, postId])
    try {
      const response = await fetch(buildComunPostCategoryUrl(comun.slug, postId), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ category_id: categoryId }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось обновить категорию')
      }
      const assignment = payload?.assignment
      posts = posts.map((post) => {
        if (post.id !== postId) return post
        return {
          ...post,
          comun_category_id: assignment?.category_id ?? null,
          comun_category: assignment?.category ?? null,
        }
      })
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Ошибка обновления категории')
    } finally {
      const next = new Set(categorySavingPostIds)
      next.delete(postId)
      categorySavingPostIds = next
    }
  }

  const onPostCategoryChange = (event: Event, postId: number) => {
    const target = event.currentTarget as HTMLSelectElement | null
    if (!target) return
    const value = target.value ? Number(target.value) : null
    void updatePostCategory(postId, value)
  }

  $: wantsSettingsOpenFromUrl = $page.url.searchParams.get('settings') === '1'

  $: if (browser && comun?.slug && $siteToken && $siteToken !== lastAuthRefreshToken) {
    lastAuthRefreshToken = $siteToken
    void refreshComunManage()
  }

  $: if (!$siteToken) {
    lastAuthRefreshToken = null
    autoSettingsOpenHandled = false
  }

  $: if (!wantsSettingsOpenFromUrl) {
    autoSettingsOpenHandled = false
  }

  $: if (
    browser &&
    wantsSettingsOpenFromUrl &&
    $siteToken &&
    !settingsOpen &&
    !autoSettingsOpenHandled &&
    !settingsLoading
  ) {
    autoSettingsOpenHandled = true
    void openSettings()
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

<div class="flex flex-col gap-6 max-w-4xl">
  <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 overflow-hidden">
    <div class="p-5 sm:p-6 flex flex-col gap-4">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div class="flex items-start gap-4 min-w-0">
          <div class="h-16 w-16 rounded-2xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
            {#if comun?.logo_url}
              <img src={comun.logo_url} alt={comun?.name ?? 'Логотип'} class="h-full w-full object-cover" />
            {:else}
              <div class="h-full w-full grid place-items-center text-2xl font-bold text-slate-400 dark:text-zinc-500">
                {comun?.name?.[0] ?? 'C'}
              </div>
            {/if}
          </div>
          <div class="min-w-0">
            <Header noMargin>{comun?.name ?? 'Комуна'}</Header>
            {#if comun?.product_tag}
              <div class="mt-1 text-sm text-slate-600 dark:text-zinc-400">
                Тег продукта: <span class="font-medium">#{comun.product_tag.name}</span>
              </div>
            {:else}
              <div class="mt-1 text-sm text-amber-700 dark:text-amber-300">
                Тег продукта пока не выбран. Посты в ленте не появятся, пока модератор не задаст тег.
              </div>
            {/if}
            {#if comun?.creator?.username}
              <div class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
                Создатель: @{comun.creator.username}
              </div>
            {/if}
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          {#if comun?.website_url}
            <a
              href={comun.website_url}
              target="_blank"
              rel="nofollow noopener"
              class="inline-flex items-center rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-zinc-800/60"
            >
              Сайт
            </a>
          {/if}
          {#if isModerator()}
            <Button color="ghost" on:click={openSettings}>Настройки комуны</Button>
          {/if}
        </div>
      </div>

      {#if comun?.product_description}
        <div class="text-sm leading-relaxed text-slate-700 dark:text-zinc-300 whitespace-pre-line">
          {comun.product_description}
        </div>
      {/if}

      {#if comun?.target_audience}
        <div class="text-sm text-slate-600 dark:text-zinc-400">
          <span class="font-medium text-slate-800 dark:text-zinc-200">Целевая аудитория:</span>
          {comun.target_audience}
        </div>
      {/if}

      <div class="flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          class="rounded-full px-3 py-1.5 text-sm border transition-colors {selectedCategorySlug ? 'border-slate-200 dark:border-zinc-800 hover:bg-slate-50 dark:hover:bg-zinc-800/60' : 'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300'}"
          on:click={() => setCategoryFilter('')}
          disabled={loadingCategory}
        >
          Все
        </button>
        {#each comun?.categories ?? [] as category}
          <button
            type="button"
            class="rounded-full px-3 py-1.5 text-sm border transition-colors {selectedCategorySlug === category.slug ? 'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300' : 'border-slate-200 dark:border-zinc-800 hover:bg-slate-50 dark:hover:bg-zinc-800/60'}"
            on:click={() => setCategoryFilter(category.slug)}
            disabled={loadingCategory}
            title={category.description || category.name}
          >
            {category.name}
          </button>
        {/each}
      </div>
    </div>
  </section>

  {#if comun?.welcome_post}
    <section class="rounded-2xl border border-blue-200 dark:border-blue-900/60 bg-blue-50/60 dark:bg-blue-950/20 p-4 sm:p-5">
      <div class="mb-3 text-sm font-semibold text-blue-800 dark:text-blue-300">
        Приветственный пост
      </div>
      <Post
        post={welcomePostView}
        class="rounded-2xl border border-slate-200/80 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 shadow-sm px-4 sm:px-5"
        view="cozy"
        actions={true}
        showReadMore={false}
        showFullBody={false}
        linkOverride={buildBackendPostPath(comun.welcome_post)}
        userUrlOverride={comun.welcome_post.author?.username ? `/${comun.welcome_post.author.username}` : undefined}
        communityUrlOverride={comun.welcome_post.rubric_slug ? `/rubrics/${comun.welcome_post.rubric_slug}/posts` : undefined}
        subscribeUrl={comun.welcome_post.channel_url ?? comun.welcome_post.author?.channel_url}
        subscribeLabel="Подписаться"
      />
    </section>
  {/if}

  {#if visiblePosts.length}
    <div class="flex flex-col gap-6" use:feedKeyboardShortcuts>
      {#each visiblePosts as backendPost (backendPost.id)}
        <div class="flex flex-col gap-3">
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

          {#if isModerator()}
            <div class="rounded-xl border border-slate-200 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/60 p-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div class="flex flex-col gap-1 min-w-0">
                <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">Категория внутри комуны</div>
                <div class="flex flex-wrap items-center gap-2">
                  <select
                    class="rounded-lg border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2 py-1 text-sm"
                    value={backendPost.comun_category_id ?? ''}
                    on:change={(event) => onPostCategoryChange(event, backendPost.id)}
                    disabled={categorySavingPostIds.has(backendPost.id)}
                  >
                    <option value="">Без категории</option>
                    {#each comun?.categories ?? [] as category}
                      <option value={category.id}>{category.name}</option>
                    {/each}
                  </select>
                  {#if backendPost.comun_category}
                    <span class="text-xs rounded-full bg-slate-100 dark:bg-zinc-800 px-2 py-1">
                      {backendPost.comun_category.name}
                    </span>
                  {/if}
                </div>
              </div>
              <div class="flex flex-wrap gap-2">
                <Button
                  color="ghost"
                  size="sm"
                  on:click={() => setWelcomePost(backendPost.id)}
                >
                  Сделать приветственным
                </Button>
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </div>
    {#if loadingMore}
      <div class="text-sm text-slate-500">Загрузка...</div>
    {/if}
  {:else}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-slate-600 dark:text-zinc-400">
      {#if comun?.product_tag}
        В этой комуне пока нет публикаций по тегу #{comun.product_tag.name}.
      {:else}
        Модератору нужно выбрать тег продукта в настройках комуны, чтобы сюда начали попадать посты.
      {/if}
    </div>
  {/if}
</div>

<Modal bind:open={settingsOpen}>
  <div class="w-full max-w-3xl flex flex-col gap-4">
    <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Настройки комуны</div>
    {#if settingsError}
      <div class="rounded-xl border border-rose-200 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-950/20 px-3 py-2 text-sm text-rose-700 dark:text-rose-300">
        {settingsError}
      </div>
    {/if}

    {#if settingsLoading}
      <div class="text-sm text-slate-500">Загрузка настроек...</div>
    {:else if settingsDraft}
      <div class="grid gap-4">
        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Веб-сайт</span>
          <input bind:value={settingsDraft.website_url} type="url" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2" />
        </label>

        <div class="flex flex-col gap-2">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Логотип</span>
          <input
            bind:this={settingsLogoInput}
            type="file"
            accept="image/*"
            class="hidden"
            on:change={onSettingsLogoSelected}
          />
          <div class="flex items-center gap-3 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-3">
            <div class="h-14 w-14 rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
              {#if settingsDraft.logo_url}
                <img src={settingsDraft.logo_url} alt="Предпросмотр логотипа" class="h-full w-full object-cover" />
              {:else}
                <div class="h-full w-full grid place-items-center text-slate-400 dark:text-zinc-500 text-xs text-center px-1">
                  Нет лого
                </div>
              {/if}
            </div>
            <div class="min-w-0 flex-1 flex flex-col gap-1">
              <div class="text-sm text-slate-700 dark:text-zinc-300">
                {#if settingsLogoUploading}
                  Загрузка логотипа...
                {:else if settingsDraft.logo_url}
                  Логотип выбран
                {:else}
                  Загрузите файл изображения
                {/if}
              </div>
              <div class="text-xs text-slate-500 dark:text-zinc-400">
                PNG, JPG, WEBP, GIF
              </div>
            </div>
            <div class="flex flex-wrap gap-2 justify-end">
              <Button size="sm" on:click={pickSettingsLogo} disabled={settingsSaving || settingsLogoUploading}>
                {settingsDraft.logo_url ? 'Заменить' : 'Выбрать файл'}
              </Button>
              {#if settingsDraft.logo_url}
                <Button
                  color="ghost"
                  size="sm"
                  on:click={() => (settingsDraft = { ...settingsDraft, logo_url: '' })}
                  disabled={settingsSaving || settingsLogoUploading}
                >
                  Убрать
                </Button>
              {/if}
            </div>
          </div>
        </div>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Описание продукта</span>
          <textarea bind:value={settingsDraft.product_description} rows="4" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"></textarea>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Целевая аудитория</span>
          <textarea bind:value={settingsDraft.target_audience} rows="2" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"></textarea>
        </label>

        <div class="flex flex-col gap-2">
          <div class="text-sm text-slate-700 dark:text-zinc-300">Тег продукта (посты с этим тегом попадут в коммуну)</div>
          <div class="flex flex-wrap items-center gap-2">
            {#if settingsDraft.product_tag}
              <span class="rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1 text-sm">
                #{settingsDraft.product_tag.name}
              </span>
              <Button color="ghost" size="sm" on:click={clearDraftTag}>Сбросить</Button>
            {:else}
              <span class="text-sm text-slate-500 dark:text-zinc-400">Тег не выбран</span>
            {/if}
          </div>
          <input
            bind:value={settingsTagSearch}
            placeholder="Поиск тега..."
            class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
          />
          <div class="max-h-48 overflow-auto rounded-xl border border-slate-200 dark:border-zinc-800 divide-y divide-slate-100 dark:divide-zinc-800">
            {#if filteredTagOptions.length}
              {#each filteredTagOptions as tag}
                <div class="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                  <div class="min-w-0">
                    <div class="font-medium text-slate-900 dark:text-zinc-100 truncate">{tag.name}</div>
                    {#if tag.lemma}
                      <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">{tag.lemma}</div>
                    {/if}
                  </div>
                  <Button size="sm" on:click={() => chooseDraftTag(tag)}>Выбрать</Button>
                </div>
              {/each}
            {:else}
              <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">Ничего не найдено</div>
            {/if}
          </div>
        </div>

        <div class="flex flex-col gap-2">
          <div class="text-sm text-slate-700 dark:text-zinc-300">Внутренние категории</div>
          <div class="grid gap-2 sm:grid-cols-2">
            {#each settingsCategoryOptions as category}
              <label class="rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2 flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={draftCategoryIdSet.has(category.id)}
                  on:change={() => toggleDraftCategory(category.id)}
                  class="mt-0.5"
                />
                <span class="min-w-0">
                  <span class="block text-sm font-medium text-slate-900 dark:text-zinc-100">{category.name}</span>
                  {#if category.description}
                    <span class="block text-xs text-slate-500 dark:text-zinc-400">{category.description}</span>
                  {/if}
                </span>
              </label>
            {/each}
          </div>
        </div>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Приветственный пост (ID или ссылка на пост)</span>
          <input
            bind:value={settingsDraft.welcome_post_ref}
            placeholder="/b/post/123... или 123"
            class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
          />
        </label>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <Button color="ghost" on:click={() => (settingsOpen = false)} disabled={settingsSaving}>Закрыть</Button>
        <Button on:click={saveSettings} disabled={settingsSaving || settingsLogoUploading}>
          {settingsSaving ? 'Сохраняем...' : 'Сохранить'}
        </Button>
      </div>
    {/if}
  </div>
</Modal>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  {#if comun?.logo_url}
    <meta property="og:image" content={comun.logo_url} />
    <meta name="twitter:image" content={comun.logo_url} />
    <meta name="twitter:card" content="summary_large_image" />
  {/if}
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
