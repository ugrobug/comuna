<script lang="ts">
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Modal, toast } from 'mono-svelte'
  import {
    buildComunsSidebarUrl,
    buildComunsUrl,
    buildTagsEnsureUrl,
    type BackendComun,
  } from '$lib/api/backend'
  import { refreshSiteUser, siteToken, siteUser, uploadSiteImage } from '$lib/siteAuth'
  import { goto } from '$app/navigation'
  import { feedSettingsHydrated, subscribeToComunBySlug, userSettings } from '$lib/settings'
  import { onMount } from 'svelte'
  import { cachedJson } from '$lib/api/publicCache'
  import { sortComunsByRating } from '$lib/communitySidebar'
  import ComunCatalogCard from '$lib/components/comuns/ComunCatalogCard.svelte'
  import RecommendedComunsPanel from '$lib/components/feeds/RecommendedComunsPanel.svelte'

  export let data

  const COMMUNITY_CREATION_MIN_AUTHOR_RATING = 0
  const COMMUNITIES_LANDING_HREF = '/lp/communities'
  const COMUNS_PAGE_SIZE = 20
  type CatalogScope = 'all' | 'mine'

  let comuns: BackendComun[] = data.comuns ?? []
  let searchQuery = data.query ?? ''
  let lastDataQuery = data.query ?? ''
  let mineComuns: BackendComun[] = []
  let mineBaseComuns: BackendComun[] = []
  let mineSourceComuns: BackendComun[] = []
  let mineHasBaseComuns = false
  let minePage = 1
  let mineTotalComuns = 0
  let mineTotalPages = 0
  let mineHasNext = false
  let mineHasPrevious = false
  let mineLoading = false
  let mineError = ''
  let sidebarIndexComuns: BackendComun[] = []
  let sidebarIndexLoaded = false
  let sidebarIndexLoading = false
  let sidebarIndexError = ''
  let createOpen = false
  let insufficientOpen = false
  let creating = false
  let createIntentHandled = false

  let name = ''
  let logoUrl = ''
  let logoUploading = false
  let createTagInput = ''
  let createTagSaving = false
  let description = ''
  let createTags: Array<{ id: number; name: string; lemma?: string | null }> = []
  let createLogoInput: HTMLInputElement | null = null

  const formatRatingValue = (value?: number | null) => {
    const numeric = Math.max(Number(value ?? 0) || 0, 0)
    return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(2).replace(/\.?0+$/, '')
  }

  const normalizeComunSlug = (slug?: string | null) => String(slug ?? '').trim().toLowerCase()

  $: myFeedComunSlugSet = new Set(
    ($userSettings.myFeedComuns ?? []).map(normalizeComunSlug).filter(Boolean)
  )
  $: selectedMyFeedComuns = $userSettings.myFeedComuns ?? []
  $: activeScope = (data.scope === 'mine' ? 'mine' : 'all') as CatalogScope
  $: requestedPage = Math.max(Number(data.page ?? 1) || 1, 1)
  $: mineBaseComuns = (() => {
    if (!$siteToken || !$feedSettingsHydrated) return []
    return sortComunsByRating(sidebarIndexComuns)
      .filter((comun) => myFeedComunSlugSet.has(normalizeComunSlug(comun.slug)) || Boolean(comun.can_moderate))
  })()
  $: mineHasBaseComuns = mineBaseComuns.length > 0
  $: mineSourceComuns = (() => {
    const query = String(data.query ?? '').trim().toLowerCase()
    return mineBaseComuns
      .filter((comun) => {
        if (!query) return true
        const name = (comun.name || '').toLowerCase()
        const description = (comun.product_description || '').toLowerCase()
        return name.includes(query) || description.includes(query)
      })
  })()
  $: if (activeScope === 'mine') {
    mineTotalComuns = mineSourceComuns.length
    mineTotalPages = Math.ceil(mineTotalComuns / COMUNS_PAGE_SIZE)
    minePage = mineTotalPages > 0 ? Math.min(requestedPage, mineTotalPages) : requestedPage
    mineHasPrevious = minePage > 1 && mineTotalComuns > 0
    mineHasNext = minePage * COMUNS_PAGE_SIZE < mineTotalComuns
    mineComuns = mineSourceComuns.slice(
      (minePage - 1) * COMUNS_PAGE_SIZE,
      minePage * COMUNS_PAGE_SIZE
    )
    mineLoading = Boolean($siteToken) && (!$feedSettingsHydrated || (!sidebarIndexLoaded && !sidebarIndexError))
    mineError = !$siteToken ? 'auth_required' : sidebarIndexError
  }
  $: comuns = activeScope === 'mine' ? mineComuns : data.comuns ?? []
  $: currentPage =
    activeScope === 'mine' ? minePage : requestedPage
  $: totalComuns =
    activeScope === 'mine' ? mineTotalComuns : Math.max(Number(data.totalComuns ?? 0) || 0, 0)
  $: totalPages =
    activeScope === 'mine' ? mineTotalPages : Math.max(Number(data.totalPages ?? 0) || 0, 0)
  $: hasNext = activeScope === 'mine' ? mineHasNext : Boolean(data.hasNext)
  $: hasPrevious = activeScope === 'mine' ? mineHasPrevious : Boolean(data.hasPrevious)
  $: if ((data.query ?? '') !== lastDataQuery) {
    lastDataQuery = data.query ?? ''
    searchQuery = lastDataQuery
  }

  onMount(() => {
    if ($siteToken && !$siteUser) {
      void refreshSiteUser().catch(() => null)
    }
  })

  const toggleComunSubscription = (comun: BackendComun) => {
    const slug = String(comun.slug ?? '').trim()
    if (!slug) return
    if (!$siteToken) {
      const next = encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)
      goto(`/account?next=${next}`)
      return
    }

    const nextComuns = new Set(
      ($userSettings.myFeedComuns ?? []).map((value) => value.trim()).filter(Boolean)
    )
    const currentSlug = Array.from(nextComuns).find((value) => normalizeComunSlug(value) === normalizeComunSlug(slug))
    const nextCategoryMap = { ...($userSettings.myFeedComunCategories ?? {}) }
    if (currentSlug) {
      nextComuns.delete(currentSlug)
      delete nextCategoryMap[currentSlug]
      $userSettings = {
        ...$userSettings,
        myFeedComuns: Array.from(nextComuns),
        myFeedComunCategories: nextCategoryMap,
      }
      toast({ content: 'Сообщество убрано из "Моей ленты"' })
      return
    }

    nextComuns.add(slug)
    $userSettings = {
      ...$userSettings,
      myFeedComuns: Array.from(nextComuns),
      myFeedComunCategories: nextCategoryMap,
    }
    toast({ content: 'Посты этого сообщества будут попадать в "Мою ленту"' })
  }

  const loadSidebarIndexComuns = async () => {
    if (!browser || sidebarIndexLoading || sidebarIndexLoaded) return
    sidebarIndexLoading = true
    sidebarIndexError = ''
    try {
      const payload = await cachedJson<{ comuns?: BackendComun[] }>(
        'public:sidebar-comuns',
        buildComunsSidebarUrl(),
        { ttlMs: 21_600_000 }
      )
      sidebarIndexComuns = payload.comuns ?? []
      sidebarIndexLoaded = true
    } catch (error) {
      sidebarIndexError = error instanceof Error ? error.message : 'Не удалось загрузить мои сообщества'
    } finally {
      sidebarIndexLoading = false
    }
  }

  $: if (browser && activeScope === 'mine' && $siteToken) {
    void loadSidebarIndexComuns()
  }

  const gotoCatalogScope = (scope: CatalogScope) => {
    const params = new URLSearchParams()
    const query = searchQuery.trim()
    if (scope === 'mine') params.set('scope', 'mine')
    if (query) params.set('q', query)
    const queryString = params.toString()
    goto(`/comuns${queryString ? `?${queryString}` : ''}`)
  }

  const gotoCatalogPage = (pageNumber: number) => {
    const nextPage = Math.max(pageNumber, 1)
    const params = new URLSearchParams()
    const query = searchQuery.trim()
    if (activeScope === 'mine') params.set('scope', 'mine')
    if (query) params.set('q', query)
    if (nextPage > 1) params.set('page', String(nextPage))
    const queryString = params.toString()
    goto(`/comuns${queryString ? `?${queryString}` : ''}`)
  }

  const submitSearch = () => {
    gotoCatalogPage(1)
  }

  const currentUserMaxAuthorRating = (user = $siteUser) => {
    const authorRatings = (user?.authors ?? []).map((author) => Math.max(Number(author.author_rating ?? 0) || 0, 0))
    const explicitRating = Math.max(Number(user?.max_author_rating ?? 0) || 0, 0)
    return Math.max(explicitRating, ...authorRatings, 0)
  }

  const canCreate = (user = $siteUser) => {
    if (!$siteToken) return false
    if (user?.is_staff) return true
    return Boolean(user?.can_create_comun ?? currentUserMaxAuthorRating(user) >= COMMUNITY_CREATION_MIN_AUTHOR_RATING)
  }

  const resetForm = () => {
    name = ''
    logoUrl = ''
    logoUploading = false
    createTagInput = ''
    createTagSaving = false
    createTags = []
    description = ''
  }

  const normalizeTagInput = (value: string) =>
    value.trim().replace(/^#+/, '').replace(/\s+/g, ' ').trim()

  const removeCreateTag = (tagId: number) => {
    createTags = createTags.filter((tag) => tag.id !== tagId)
  }

  const addCreateTag = async () => {
    const tagName = normalizeTagInput(createTagInput)
    if (!tagName || createTagSaving) return
    if (createTags.length >= 5) {
      toast({ content: 'Можно добавить не больше 5 тегов', type: 'warning' })
      return
    }
    createTagSaving = true
    try {
      const response = await fetch(buildTagsEnsureUrl(), {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ name: tagName }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || !payload?.tag?.id) {
        throw new Error(payload?.error || 'Не удалось добавить тег')
      }
      const nextTag = {
        id: Number(payload.tag.id),
        name: String(payload.tag.name ?? tagName),
        lemma: payload.tag.lemma ? String(payload.tag.lemma) : null,
      }
      if (createTags.some((tag) => tag.id === nextTag.id)) {
        createTagInput = ''
        return
      }
      createTags = [...createTags, nextTag].slice(0, 5)
      createTagInput = ''
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Не удалось добавить тег', type: 'error' })
    } finally {
      createTagSaving = false
    }
  }

  const onCreateTagKeydown = (event: KeyboardEvent) => {
    if (event.key !== 'Enter') return
    event.preventDefault()
    void addCreateTag()
  }

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  const openCreate = async () => {
    if (!canCreate()) {
      if (!$siteToken) {
        goto('/account?next=/comuns?create=1')
        return
      }

      const user = $siteUser ?? (await refreshSiteUser())
      if (!user) {
        goto('/account?next=/comuns?create=1')
        return
      }
      if (!canCreate(user)) {
        insufficientOpen = true
        return
      }
    }
    createOpen = true
  }

  $: if (browser && $page.url.searchParams.get('create') === '1' && !createIntentHandled) {
    createIntentHandled = true
    void openCreate()
  }

  $: if (browser && $page.url.searchParams.get('create') !== '1') {
    createIntentHandled = false
  }

  const pickCreateLogo = () => {
    if (!canCreate()) {
      void openCreate()
      return
    }
    createLogoInput?.click()
  }

  const onCreateLogoSelected = async (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    const file = input?.files?.[0]
    if (!file) return

    logoUploading = true
    try {
      const uploadedUrl = await uploadSiteImage(file)
      logoUrl = uploadedUrl
      toast({ content: 'Логотип загружен', type: 'success' })
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Не удалось загрузить логотип', type: 'error' })
    } finally {
      logoUploading = false
      if (input) input.value = ''
    }
  }

  const createComun = async () => {
    if (!name.trim()) {
      toast({ content: 'Введите название сообщества', type: 'warning' })
      return
    }
    creating = true
    try {
      const response = await fetch(buildComunsUrl(), {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          name,
          logo_url: logoUrl,
          description,
          product_description: description,
          tag_ids: createTags.map((tag) => tag.id),
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || !payload?.comun?.slug) {
        if (payload?.reason === 'insufficient_author_rating') {
          insufficientOpen = true
          throw new Error('У вас недостаточно рейтинга для создания сообщества')
        }
        throw new Error(payload?.error || 'Не удалось создать сообщество')
      }
      createOpen = false
      resetForm()
      subscribeToComunBySlug(payload.comun.slug)
      toast({ content: 'Сообщество создано', type: 'success' })
      goto(`/comuns/${payload.comun.slug}/settings`)
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Ошибка создания', type: 'error' })
    } finally {
      creating = false
    }
  }
</script>

<div class="flex flex-col gap-6 max-w-4xl">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="min-w-0">
      <Header noMargin>Сообщества</Header>
    </div>
    <Button on:click={() => void openCreate()}>
      {#if $siteUser}
        Создать сообщество
      {:else}
        Войти и создать
      {/if}
    </Button>
  </div>

  <div class="inline-flex w-fit rounded-xl border border-slate-200 bg-white p-1 text-sm dark:border-zinc-800 dark:bg-zinc-900">
    <button
      type="button"
      class={`rounded-lg px-4 py-2 font-medium transition ${
        activeScope === 'all'
          ? 'bg-slate-900 text-white dark:bg-zinc-100 dark:text-zinc-950'
          : 'text-slate-600 hover:bg-slate-50 dark:text-zinc-300 dark:hover:bg-zinc-800'
      }`}
      on:click={() => gotoCatalogScope('all')}
    >
      Все сообщества
    </button>
    <button
      type="button"
      class={`rounded-lg px-4 py-2 font-medium transition ${
        activeScope === 'mine'
          ? 'bg-slate-900 text-white dark:bg-zinc-100 dark:text-zinc-950'
          : 'text-slate-600 hover:bg-slate-50 dark:text-zinc-300 dark:hover:bg-zinc-800'
      }`}
      on:click={() => gotoCatalogScope('mine')}
    >
      Мои сообщества
    </button>
  </div>

  <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 sm:p-5">
    <form class="flex flex-col gap-3 sm:flex-row" on:submit|preventDefault={submitSearch}>
      <label class="min-w-0 flex-1">
        <span class="sr-only">Поиск сообществ</span>
        <input
          bind:value={searchQuery}
          type="text"
          placeholder="Поиск сообществ"
          class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500"
        />
      </label>
      <div class="flex shrink-0 gap-2">
        <button
          type="submit"
          class="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-zinc-100 dark:text-zinc-950 dark:hover:bg-zinc-300"
        >
          Найти
        </button>
        {#if data.query}
          <button
            type="button"
            class="rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
            on:click={() => {
              searchQuery = ''
              gotoCatalogPage(1)
            }}
          >
            Сбросить
          </button>
        {/if}
      </div>
    </form>
  </section>

  {#if activeScope === 'mine' && mineLoading}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-slate-600 dark:text-zinc-400">
      Загрузка...
    </div>
  {:else if activeScope === 'mine' && mineError === 'auth_required'}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-slate-600 dark:text-zinc-400">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span>Войдите, чтобы открыть свои сообщества.</span>
        <a
          href={`/account?next=${encodeURIComponent('/comuns?scope=mine')}`}
          class="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-zinc-100 dark:text-zinc-950 dark:hover:bg-zinc-300"
        >
          Войти
        </a>
      </div>
    </div>
  {:else if activeScope === 'mine' && mineError}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-red-600 dark:text-red-400">
      {mineError}
    </div>
  {:else if comuns.length}
    <div class="grid gap-4 sm:grid-cols-2">
      {#each comuns as comun}
        {@const subscribed = myFeedComunSlugSet.has(normalizeComunSlug(comun.slug))}
        {@const subscriptionsLoading = Boolean($siteToken && !$feedSettingsHydrated)}
        <ComunCatalogCard
          {comun}
          {subscribed}
          {subscriptionsLoading}
          on:toggle={() => toggleComunSubscription(comun)}
        />
      {/each}
    </div>
  {:else if activeScope === 'mine' && !mineHasBaseComuns}
    <RecommendedComunsPanel
      selectedSlugs={selectedMyFeedComuns}
      title="Подпишитесь на сообщества"
      description="Выберите несколько сообществ, чтобы они появились здесь и начали наполнять вашу ленту."
    />
  {:else}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-slate-600 dark:text-zinc-400">
      {#if data.query}
        Ничего не найдено по вашему запросу.
      {:else if activeScope === 'mine'}
        У вас пока нет сообществ.
      {:else}
        Пока нет созданных сообществ.
      {/if}
    </div>
  {/if}

  {#if totalComuns > 0}
    <div class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white/95 p-3 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900/85 dark:text-zinc-400">
      <div>
        {currentPage} / {Math.max(totalPages, 1)}
      </div>
      <div class="flex gap-2">
        <button
          type="button"
          class="rounded-xl border border-slate-300 px-4 py-2 font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
          disabled={!hasPrevious}
          on:click={() => gotoCatalogPage(currentPage - 1)}
        >
          Назад
        </button>
        <button
          type="button"
          class="rounded-xl border border-slate-300 px-4 py-2 font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
          disabled={!hasNext}
          on:click={() => gotoCatalogPage(currentPage + 1)}
        >
          Вперед
        </button>
      </div>
    </div>
  {/if}
</div>

<Modal bind:open={createOpen} on:close={resetForm}>
  <div class="w-full max-w-2xl flex flex-col gap-4">
    <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Создать сообщество</div>
    <div class="text-sm text-slate-600 dark:text-zinc-400">
      После создания откроются настройки сообщества, где можно донастроить категории, теги, модераторов, приветственный пост и многое другое.
    </div>

    <label class="flex flex-col gap-1">
      <span class="text-sm text-slate-700 dark:text-zinc-300">Название</span>
      <input bind:value={name} class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2" />
    </label>

    <div class="flex flex-col gap-2">
      <span class="text-sm text-slate-700 dark:text-zinc-300">Логотип</span>
      <input
        bind:this={createLogoInput}
        type="file"
        accept="image/*"
        class="hidden"
        on:change={onCreateLogoSelected}
      />
      <div class="flex items-center gap-3 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-3">
        <div class="h-14 w-14 rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
          {#if logoUrl}
            <img src={logoUrl} alt="Предпросмотр логотипа" class="h-full w-full object-cover" />
          {:else}
            <div class="h-full w-full grid place-items-center text-slate-400 dark:text-zinc-500 text-xs text-center px-1">
              Нет лого
            </div>
          {/if}
        </div>
        <div class="min-w-0 flex-1 flex flex-col gap-1">
          <div class="text-sm text-slate-700 dark:text-zinc-300">
            {#if logoUploading}
              Загрузка логотипа...
            {:else if logoUrl}
              Логотип загружен
            {:else}
              Загрузите файл изображения
            {/if}
          </div>
          <div class="text-xs text-slate-500 dark:text-zinc-400">
            PNG, JPG, WEBP, GIF
          </div>
        </div>
        <div class="flex flex-wrap gap-2 justify-end">
          <Button on:click={pickCreateLogo} disabled={creating || logoUploading} size="sm">
            {logoUrl ? 'Заменить' : 'Выбрать файл'}
          </Button>
          {#if logoUrl}
            <Button color="ghost" size="sm" on:click={() => (logoUrl = '')} disabled={creating || logoUploading}>
              Убрать
            </Button>
          {/if}
        </div>
      </div>
    </div>

    <label class="flex flex-col gap-1">
      <span class="text-sm text-slate-700 dark:text-zinc-300">Описание</span>
      <textarea bind:value={description} rows="4" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"></textarea>
    </label>

    <div class="flex flex-col gap-3">
      <div class="flex items-start justify-between gap-3">
        <div>
          <div class="text-sm text-slate-700 dark:text-zinc-300">Теги</div>
          <div class="text-xs text-slate-500 dark:text-zinc-400">
            До 5 тегов для удобства поиска и сортировки сообщества.
          </div>
        </div>
        <div class="text-xs text-slate-500 dark:text-zinc-400">{createTags.length}/5</div>
      </div>
      <div class="flex gap-2">
        <input
          bind:value={createTagInput}
          placeholder="Например: saas, дизайн, аналитика"
          class="flex-1 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
          on:keydown={onCreateTagKeydown}
          disabled={createTagSaving || createTags.length >= 5}
        />
        <Button on:click={() => void addCreateTag()} disabled={createTagSaving || !createTagInput.trim() || createTags.length >= 5}>
          {createTagSaving ? 'Добавляем...' : 'Добавить'}
        </Button>
      </div>
      {#if createTags.length}
        <div class="flex flex-wrap gap-2">
          {#each createTags as tag}
            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-full border border-slate-200 dark:border-zinc-700 bg-slate-50 dark:bg-zinc-900 px-3 py-1 text-sm text-slate-700 dark:text-zinc-200"
              on:click={() => removeCreateTag(tag.id)}
            >
              <span>#{tag.name}</span>
              <span class="text-slate-400 dark:text-zinc-500">×</span>
            </button>
          {/each}
        </div>
      {/if}
    </div>

    <div class="flex justify-end gap-2 pt-2">
      <Button color="ghost" on:click={() => (createOpen = false)} disabled={creating}>Отмена</Button>
      <Button on:click={createComun} disabled={creating || logoUploading}>
        {creating ? 'Создаем...' : 'Создать сообщество'}
      </Button>
    </div>
  </div>
</Modal>

<Modal bind:open={insufficientOpen}>
  <div class="w-full max-w-xl flex flex-col gap-4">
    <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Недостаточно рейтинга</div>
    <div class="text-sm leading-6 text-slate-600 dark:text-zinc-400">
      У вас недостаточно рейтинга для создания сообщества. Сейчас ваш максимальный рейтинг автора:
      <span class="font-semibold text-slate-900 dark:text-zinc-100">{formatRatingValue(currentUserMaxAuthorRating())}</span>.
      Для создания нужен неотрицательный рейтинг автора.
    </div>
    <div class="grid gap-3">
      <a
        href={COMMUNITIES_LANDING_HREF}
        class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-900 px-4 py-4 text-sm font-medium text-slate-900 dark:text-zinc-100 hover:border-slate-300 dark:hover:border-zinc-700 transition-colors"
      >
        Что такое сообщества
      </a>
    </div>
    <div class="flex justify-end gap-2 pt-1">
      <Button color="ghost" on:click={() => (insufficientOpen = false)}>Закрыть</Button>
    </div>
  </div>
</Modal>
