<script lang="ts">
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Modal, toast } from 'mono-svelte'
  import { buildComunsUrl, buildTagsEnsureUrl, type BackendComun } from '$lib/api/backend'
  import { refreshSiteUser, siteToken, siteUser, uploadSiteImage } from '$lib/siteAuth'
  import { goto } from '$app/navigation'
  import { feedSettingsHydrated, subscribeToComunBySlug, userSettings } from '$lib/settings'
  import { onMount } from 'svelte'

  export let data

  const COMMUNITY_CREATION_MIN_AUTHOR_RATING = 0
  const COMMUNITIES_LANDING_HREF = '/lp/communities'

  let comuns: BackendComun[] = data.comuns ?? []
  let filteredComuns: BackendComun[] = []
  let searchQuery = ''
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

  const hashString = (value?: string | null) => {
    const source = (value ?? '').trim() || 'comuna'
    let hash = 0
    for (let i = 0; i < source.length; i += 1) {
      hash = (hash * 31 + source.charCodeAt(i)) % 360
    }
    return Math.abs(hash)
  }

  const comunPlaceholderStyle = (name?: string | null) => `--comun-h:${hashString(name)}`

  const comunInitial = (name?: string | null) =>
    (name ?? '').trim().slice(0, 1).toUpperCase() || 'C'

  const formatRatingValue = (value?: number | null) => {
    const numeric = Math.max(Number(value ?? 0) || 0, 0)
    return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(2).replace(/\.?0+$/, '')
  }

  const normalizeComunSlug = (slug?: string | null) => String(slug ?? '').trim().toLowerCase()

  $: myFeedComunSlugSet = new Set(
    ($userSettings.myFeedComuns ?? []).map(normalizeComunSlug).filter(Boolean)
  )

  onMount(() => {
    if ($siteToken && !$siteUser) {
      void refreshSiteUser().catch(() => null)
    }
  })

  const comunCategorySlugs = (comun: BackendComun) =>
    (comun.categories ?? [])
      .map((category) => String(category?.slug ?? '').trim())
      .filter(Boolean)

  const toggleComunSubscription = (event: MouseEvent, comun: BackendComun) => {
    event.preventDefault()
    event.stopPropagation()

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
    const categorySlugs = comunCategorySlugs(comun)
    if (categorySlugs.length) {
      nextCategoryMap[slug] = categorySlugs
    }
    $userSettings = {
      ...$userSettings,
      myFeedComuns: Array.from(nextComuns),
      myFeedComunCategories: nextCategoryMap,
    }
    toast({ content: 'Посты этого сообщества будут попадать в "Мою ленту"' })
  }

  $: filteredComuns = (() => {
    const query = searchQuery.trim().toLowerCase()
    if (!query) return comuns
    return comuns.filter((comun) => {
      const name = (comun.name || '').toLowerCase()
      const description = (comun.product_description || '').toLowerCase()
      const tags = (comun.tags ?? []).map((tag) => (tag.name || '').toLowerCase()).join(' ')
      return name.includes(query) || description.includes(query) || tags.includes(query)
    })
  })()

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

  <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 sm:p-5">
    <label>
      <span class="sr-only">Поиск сообществ</span>
      <input
        bind:value={searchQuery}
        type="text"
        placeholder="Поиск сообществ"
        class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500"
      />
    </label>
  </section>

  {#if filteredComuns.length}
    <div class="grid gap-4 sm:grid-cols-2">
      {#each filteredComuns as comun}
        {@const subscribed = myFeedComunSlugSet.has(normalizeComunSlug(comun.slug))}
        {@const subscriptionsLoading = Boolean($siteToken && !$feedSettingsHydrated)}
        <div
          class="group rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 sm:p-5 hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-sm transition-all min-w-0"
        >
          <div class="flex items-start gap-4 min-w-0">
            <div class="flex shrink-0 flex-col items-center gap-2">
              <a
                href={`/comuns/${comun.slug}`}
                class="h-14 w-14 rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800"
                aria-label={`Открыть сообщество ${comun.name}`}
              >
                {#if comun.logo_url}
                  <img src={comun.logo_url} alt={comun.name} class="h-full w-full object-cover" />
                {:else}
                  <div
                    class="comun-logo-fallback h-full w-full grid place-items-center text-xl font-bold"
                    style={comunPlaceholderStyle(comun.name)}
                  >
                    {comunInitial(comun.name)}
                  </div>
                {/if}
              </a>
              <button
                type="button"
                class={`grid h-9 w-9 place-items-center rounded-full border transition ${
                  subscribed
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300'
                    : 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 dark:border-blue-900/70 dark:bg-blue-950/40 dark:text-blue-300'
                } ${subscriptionsLoading ? 'opacity-60 cursor-wait' : ''}`}
                title={subscriptionsLoading ? 'Загружаем подписки...' : subscribed ? 'Вы подписаны' : 'Подписаться'}
                aria-label={subscribed ? `Отписаться от ${comun.name}` : `Подписаться на ${comun.name}`}
                aria-pressed={subscribed}
                disabled={subscriptionsLoading}
                on:click={(event) => toggleComunSubscription(event, comun)}
              >
                {#if subscribed}
                  <svg class="h-4 w-4" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                    <path d="M4.5 10.4 8.1 14 15.7 6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                {:else}
                  <svg class="h-4 w-4" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                    <path d="M10 4v12M4 10h12" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" />
                  </svg>
                {/if}
              </button>
            </div>
            <a href={`/comuns/${comun.slug}`} class="min-w-0 flex-1">
              <div class="flex items-center gap-2 min-w-0">
                <div class="text-base font-semibold text-slate-900 dark:text-zinc-100 truncate">
                  {comun.name}
                </div>
                {#if comun.tags?.length}
                  {#each comun.tags.slice(0, 2) as sourceTag}
                    <span class="shrink-0 rounded-full bg-slate-100 dark:bg-zinc-800 px-2 py-0.5 text-xs text-slate-600 dark:text-zinc-300">
                      #{sourceTag.name}
                    </span>
                  {/each}
                {/if}
              </div>
              {#if comun.product_description}
                <div class="mt-1 text-sm text-slate-600 dark:text-zinc-400 line-clamp-3">
                  {comun.product_description}
                </div>
              {/if}
              {#if comun.tags?.length}
                <div class="mt-3 flex flex-wrap gap-2">
                  {#each comun.tags.slice(0, 4) as tag}
                    <span class="rounded-full bg-slate-100 dark:bg-zinc-800 px-2 py-1 text-xs text-slate-600 dark:text-zinc-300">
                      #{tag.name}
                    </span>
                  {/each}
                  {#if comun.tags.length > 4}
                    <span class="rounded-full bg-slate-100 dark:bg-zinc-800 px-2 py-1 text-xs text-slate-500 dark:text-zinc-400">
                      +{comun.tags.length - 4}
                    </span>
                  {/if}
                </div>
              {/if}
            </a>
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-slate-600 dark:text-zinc-400">
      {#if comuns.length}
        Ничего не найдено по вашему запросу.
      {:else}
        Пока нет созданных сообществ.
      {/if}
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

<style>
  .comun-logo-fallback {
    background: hsl(var(--comun-h, 220) 60% 92%);
    color: hsl(var(--comun-h, 220) 70% 34%);
  }

  :global(.dark) .comun-logo-fallback {
    background: hsl(var(--comun-h, 220) 35% 20%);
    color: hsl(var(--comun-h, 220) 78% 72%);
  }
</style>
