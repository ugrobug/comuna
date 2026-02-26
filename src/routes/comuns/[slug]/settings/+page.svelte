<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { onMount } from 'svelte'
  import { Button, toast } from 'mono-svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import {
    buildComunUrl,
    buildTagsEnsureUrl,
    type BackendComun,
    type BackendComunCategory,
    type BackendTag,
  } from '$lib/api/backend'
  import { siteToken, uploadSiteImage } from '$lib/siteAuth'
  import { env } from '$env/dynamic/public'

  export let data

  const slug = String(data?.slug ?? '')

  let comun: BackendComun | null = null
  let settingsDraft: BackendComun | null = null
  let settingsLoading = true
  let settingsSaving = false
  let settingsLogoUploading = false
  let settingsTagCreating = false
  let settingsError = ''
  let lastAuthRefreshToken: string | null = null

  let settingsTagSearch = ''
  let settingsUserSearch = ''
  let settingsCategoryOptions: BackendComunCategory[] = []
  type ComunTagOption = BackendTag & { id: number }
  type ComunUserOption = { id: number; username: string; display_name?: string | null }
  let settingsTagOptions: ComunTagOption[] = []
  let settingsUserOptions: ComunUserOption[] = []
  let settingsLogoInput: HTMLInputElement | null = null

  const cloneComun = (value: BackendComun | null): BackendComun | null =>
    value ? JSON.parse(JSON.stringify(value)) : null

  const normalizeIds = (values: Array<number | null | undefined>) =>
    Array.from(
      new Set(
        values
          .filter((value): value is number => Number.isFinite(value as number) && Number(value) > 0)
          .map(Number)
      )
    ).sort((a, b) => a - b)

  const comunModeratorIds = (value: BackendComun | null) =>
    normalizeIds(
      ((value?.moderator_ids as number[] | undefined) ??
        (value?.moderators ?? []).map((moderator) => moderator.id ?? 0)) as number[]
    )

  const comunCategoryIds = (value: BackendComun | null) =>
    normalizeIds(
      ((value?.category_ids as number[] | undefined) ??
        (value?.categories ?? []).map((category) => category.id ?? 0)) as number[]
    )

  const settingsComparable = (value: BackendComun | null) =>
    JSON.stringify({
      website_url: (value?.website_url ?? '').trim(),
      logo_url: (value?.logo_url ?? '').trim(),
      product_description: (value?.product_description ?? '').trim(),
      target_audience: (value?.target_audience ?? '').trim(),
      include_in_public_feeds: value?.include_in_public_feeds ?? true,
      product_tag_id: value?.product_tag_id ?? value?.product_tag?.id ?? null,
      category_ids: comunCategoryIds(value),
      moderator_ids: comunModeratorIds(value),
      welcome_post_ref: String(value?.welcome_post_ref ?? value?.welcome_post_id ?? '').trim(),
    })

  const canModerate = () => Boolean(comun?.can_moderate && $siteToken)
  const canManageComunModerators = () => Boolean(comun?.can_manage_moderators && $siteToken)

  const userDisplayName = (
    user?: { username?: string | null; display_name?: string | null } | null
  ) => {
    const displayName = (user?.display_name ?? '').trim()
    if (displayName) return displayName
    const username = (user?.username ?? '').trim()
    return username ? `@${username}` : 'Пользователь'
  }

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  const refreshComunManage = async () => {
    if (!slug) return
    if (!$siteToken) {
      settingsLoading = false
      settingsError = 'Нужна авторизация'
      comun = null
      settingsDraft = null
      return
    }
    settingsLoading = true
    settingsError = ''
    try {
      const response = await fetch(buildComunUrl(slug), {
        headers: { Authorization: `Bearer ${$siteToken}` },
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        if (response.status === 401) throw new Error('Нужна авторизация')
        if (response.status === 404) throw new Error('Комуна не найдена')
        throw new Error(payload?.error || 'Не удалось загрузить настройки комуны')
      }
      if (!payload?.comun) {
        throw new Error('Комуна не найдена')
      }
      comun = payload.comun
      settingsDraft = cloneComun(payload.comun)
      settingsCategoryOptions = payload.comun?.options?.categories ?? []
      settingsTagOptions = payload.comun?.options?.tags ?? []
      settingsUserOptions = payload.comun?.options?.users ?? []
      if (!payload.comun?.can_moderate) {
        settingsError = 'Настройки доступны только модераторам комуны'
      }
    } catch (error) {
      settingsError = error instanceof Error ? error.message : 'Ошибка загрузки'
      comun = comun ?? null
      settingsDraft = settingsDraft ?? null
    } finally {
      settingsLoading = false
    }
  }

  const toggleDraftCategory = (categoryId: number) => {
    if (!settingsDraft) return
    const current = new Set(
      (settingsDraft.category_ids ?? settingsDraft.categories ?? [])
        .map((item: any) => (typeof item === 'number' ? item : item?.id))
        .filter(Boolean)
    )
    if (current.has(categoryId)) current.delete(categoryId)
    else current.add(categoryId)
    settingsDraft = { ...settingsDraft, category_ids: Array.from(current) as number[] }
  }

  const setDraftModeratorIds = (ids: number[]) => {
    if (!settingsDraft) return
    const creatorId = Number(settingsDraft.creator?.id ?? comun?.creator?.id ?? 0)
    const normalizedIds = normalizeIds([...ids, creatorId > 0 ? creatorId : 0])
    const byId = new Map<number, ComunUserOption>()
    for (const user of settingsUserOptions) byId.set(user.id, user)
    for (const moderator of settingsDraft.moderators ?? []) {
      byId.set(moderator.id, {
        id: moderator.id,
        username: moderator.username,
        display_name: moderator.display_name ?? null,
      })
    }
    settingsDraft = {
      ...settingsDraft,
      moderator_ids: normalizedIds,
      moderators: normalizedIds.map((id) => {
        const user = byId.get(id)
        return {
          id,
          username: user?.username ?? String(id),
          display_name: user?.display_name ?? null,
        }
      }),
    }
  }

  const addDraftModerator = (userId: number) => {
    if (!settingsDraft || !canManageComunModerators()) return
    setDraftModeratorIds([...comunModeratorIds(settingsDraft), userId])
  }

  const removeDraftModerator = (userId: number) => {
    if (!settingsDraft || !canManageComunModerators()) return
    setDraftModeratorIds(comunModeratorIds(settingsDraft).filter((id) => id !== userId))
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

  const onIncludeInPublicFeedsChange = (event: Event) => {
    if (!settingsDraft) return
    const input = event.currentTarget as HTMLInputElement | null
    settingsDraft = {
      ...settingsDraft,
      include_in_public_feeds: input?.checked ?? true,
    }
  }

  const normalizeTagInput = (value: string) =>
    value.trim().replace(/^#+/, '').replace(/\s+/g, ' ').trim()

  $: normalizedTagSearch = settingsTagSearch.trim().toLowerCase()
  $: normalizedTagCreateValue = normalizeTagInput(settingsTagSearch)
  $: hasExactTagMatch = (settingsTagOptions ?? []).some((tag) => {
    const needle = normalizedTagCreateValue.toLowerCase()
    if (!needle) return false
    return [tag.name, tag.lemma ?? '']
      .map((value) => normalizeTagInput(value).toLowerCase())
      .some((value) => value === needle)
  })
  $: draftCategoryIdSet = new Set<number>(
    ((settingsDraft?.category_ids as number[] | undefined) ??
      (settingsDraft?.categories ?? []).map((item) => item.id)) as number[]
  )
  $: filteredTagOptions = (settingsTagOptions ?? [])
    .filter((tag) => {
      if (!normalizedTagSearch) return true
      return [tag.name, tag.lemma ?? ''].some((value) =>
        value.toLowerCase().includes(normalizedTagSearch)
      )
    })
    .slice(0, 30)
  $: normalizedUserSearch = settingsUserSearch.trim().toLowerCase()
  $: draftModeratorIdSet = new Set<number>(comunModeratorIds(settingsDraft))
  $: settingsHasChanges = settingsComparable(settingsDraft) !== settingsComparable(comun)
  $: filteredUserOptions = (settingsUserOptions ?? [])
    .filter((user) => {
      if (!normalizedUserSearch) return true
      return [user.username, user.display_name ?? ''].some((value) =>
        value.toLowerCase().includes(normalizedUserSearch)
      )
    })
    .slice(0, 50)
  $: selectedModeratorUsers = comunModeratorIds(settingsDraft).map((id) => {
    const fromOptions = settingsUserOptions.find((user) => user.id === id)
    if (fromOptions) return fromOptions
    const fromDraft = settingsDraft?.moderators?.find((moderator) => moderator.id === id)
    return {
      id,
      username: fromDraft?.username ?? String(id),
      display_name: fromDraft?.display_name ?? null,
    }
  })

  const createTagAndChooseDraft = async () => {
    const tagName = normalizeTagInput(settingsTagSearch)
    if (!tagName || settingsTagCreating) return
    settingsTagCreating = true
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
      const nextTag: ComunTagOption = {
        id: Number(payload.tag.id),
        name: String(payload.tag.name ?? tagName),
        lemma: payload.tag.lemma ? String(payload.tag.lemma) : null,
      }
      const nextOptions = [...(settingsTagOptions ?? [])]
      const existingIndex = nextOptions.findIndex((tag) => tag.id === nextTag.id)
      if (existingIndex >= 0) nextOptions[existingIndex] = nextTag
      else nextOptions.push(nextTag)
      settingsTagOptions = nextOptions.sort((a, b) => a.name.localeCompare(b.name, 'ru'))
      chooseDraftTag(nextTag)
      settingsTagSearch = nextTag.name
      toast({
        content: payload.created ? 'Тег добавлен и выбран' : 'Тег найден и выбран',
        type: 'success',
      })
    } catch (error) {
      toast({
        content: error instanceof Error ? error.message : 'Не удалось добавить тег',
        type: 'error',
      })
    } finally {
      settingsTagCreating = false
    }
  }

  const saveSettings = async () => {
    if (!slug || !settingsDraft) return
    settingsSaving = true
    settingsError = ''
    try {
      const response = await fetch(buildComunUrl(slug), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({
          website_url: settingsDraft.website_url ?? '',
          logo_url: settingsDraft.logo_url ?? '',
          product_description: settingsDraft.product_description ?? '',
          target_audience: settingsDraft.target_audience ?? '',
          include_in_public_feeds: canManageComunModerators()
            ? settingsDraft.include_in_public_feeds ?? true
            : undefined,
          moderator_ids: canManageComunModerators() ? comunModeratorIds(settingsDraft) : undefined,
          product_tag_id: settingsDraft.product_tag_id ?? null,
          category_ids:
            settingsDraft.category_ids ??
            (settingsDraft.categories ?? []).map((category) => category.id),
          welcome_post_ref: settingsDraft.welcome_post_ref ?? '',
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось сохранить настройки')
      }
      comun = payload.comun ?? comun
      settingsDraft = cloneComun(comun)
      settingsCategoryOptions = payload.comun?.options?.categories ?? settingsCategoryOptions
      settingsTagOptions = payload.comun?.options?.tags ?? settingsTagOptions
      settingsUserOptions = payload.comun?.options?.users ?? settingsUserOptions
      toast({ content: 'Настройки комуны сохранены', type: 'success' })
    } catch (error) {
      settingsError = error instanceof Error ? error.message : 'Ошибка сохранения'
    } finally {
      settingsSaving = false
    }
  }

  const pickSettingsLogo = () => {
    if (!canModerate()) return
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
      toast({
        content: 'Логотип загружен. Сохраните настройки для применения.',
        type: 'success',
      })
    } catch (error) {
      toast({
        content: error instanceof Error ? error.message : 'Не удалось загрузить логотип',
        type: 'error',
      })
    } finally {
      settingsLogoUploading = false
      if (input) input.value = ''
    }
  }

  const openLogin = () => {
    const next = encodeURIComponent($page.url.pathname + $page.url.search)
    goto(`/account?next=${next}`)
  }

  $: if (browser && $siteToken && $siteToken !== lastAuthRefreshToken) {
    lastAuthRefreshToken = $siteToken
    void refreshComunManage()
  }

  $: if (!$siteToken) {
    lastAuthRefreshToken = null
  }

  onMount(() => {
    if (!$siteToken) {
      settingsLoading = false
      settingsError = 'Нужна авторизация'
      return
    }
    void refreshComunManage()
  })

  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Comuna'
  $: pageTitle = comun?.name
    ? `Настройки комуны ${comun.name} — ${siteTitle}`
    : `Настройки комуны — ${siteTitle}`
</script>

<div class="mx-auto flex max-w-3xl flex-col gap-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="min-w-0">
      <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">
        Комуна
      </div>
      <Header noMargin>Настройки комуны</Header>
      {#if comun?.name}
        <div class="text-sm text-slate-600 dark:text-zinc-400 truncate">{comun.name}</div>
      {/if}
    </div>
    <a
      href={slug ? `/comuns/${encodeURIComponent(slug)}` : '/comuns/'}
      class="inline-flex items-center rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-zinc-800/60"
    >
      Назад к комуне
    </a>
  </div>

  {#if settingsError}
    <div class="rounded-xl border border-rose-200 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-950/20 px-3 py-2 text-sm text-rose-700 dark:text-rose-300">
      {settingsError}
    </div>
  {/if}

  {#if settingsLoading}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-sm text-slate-500 dark:text-zinc-400">
      Загрузка настроек...
    </div>
  {:else if !$siteToken}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 flex flex-col gap-3">
      <div class="text-sm text-slate-700 dark:text-zinc-300">
        Чтобы открыть настройки комуны, нужно войти в аккаунт.
      </div>
      <div>
        <Button on:click={openLogin}>Войти</Button>
      </div>
    </div>
  {:else if !canModerate()}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-sm text-slate-700 dark:text-zinc-300">
      Настройки доступны только создателю или назначенным модераторам этой комуны.
    </div>
  {:else if settingsDraft}
    <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-5 sm:p-6">
      <div class="grid gap-4">
        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Веб-сайт</span>
          <input
            bind:value={settingsDraft.website_url}
            type="url"
            class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
          />
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
              <div class="text-xs text-slate-500 dark:text-zinc-400">PNG, JPG, WEBP, GIF</div>
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
          <textarea
            bind:value={settingsDraft.product_description}
            rows="4"
            class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
          ></textarea>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Целевая аудитория</span>
          <textarea
            bind:value={settingsDraft.target_audience}
            rows="2"
            class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
          ></textarea>
        </label>

        {#if canManageComunModerators()}
          <label class="rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-3 flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              class="mt-1"
              checked={settingsDraft.include_in_public_feeds ?? true}
              on:change={onIncludeInPublicFeedsChange}
            />
            <span class="min-w-0">
              <span class="block text-sm font-medium text-slate-900 dark:text-zinc-100">
                Показывать посты этой комуны в Горячем и Свежее
              </span>
              <span class="block text-xs text-slate-500 dark:text-zinc-400">
                Если выключить, посты, созданные внутри комуны, останутся только в ленте комуны и персональных лентах пользователей.
              </span>
            </span>
          </label>
        {/if}

        {#if canManageComunModerators()}
          <div class="flex flex-col gap-2">
            <div class="text-sm text-slate-700 dark:text-zinc-300">Модераторы комуны</div>
            <div class="text-xs text-slate-500 dark:text-zinc-400">
              Только создатель комуны может назначать и снимать модераторов. Создатель всегда остается модератором.
            </div>
            <input
              bind:value={settingsUserSearch}
              placeholder="Поиск пользователя по имени или логину..."
              class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            />
            <div class="max-h-52 overflow-auto rounded-xl border border-slate-200 dark:border-zinc-800 divide-y divide-slate-100 dark:divide-zinc-800">
              {#if filteredUserOptions.length}
                {#each filteredUserOptions as user}
                  <div class="flex items-center justify-between gap-2 px-3 py-2">
                    <div class="min-w-0">
                      <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">
                        {userDisplayName(user)}
                      </div>
                      <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">@{user.username}</div>
                    </div>
                    <Button size="sm" on:click={() => addDraftModerator(user.id)} disabled={draftModeratorIdSet.has(user.id)}>
                      {draftModeratorIdSet.has(user.id) ? 'Добавлен' : 'Добавить'}
                    </Button>
                  </div>
                {/each}
              {:else}
                <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">Пользователи не найдены</div>
              {/if}
            </div>
            <div class="flex flex-col gap-2">
              <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">
                Выбранные модераторы
              </div>
              <div class="flex flex-col gap-2">
                {#each selectedModeratorUsers as user}
                  <div class="flex items-center justify-between gap-2 rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2">
                    <div class="min-w-0">
                      <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">
                        {userDisplayName(user)}
                      </div>
                      <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">@{user.username}</div>
                    </div>
                    <Button
                      color="ghost"
                      size="sm"
                      on:click={() => removeDraftModerator(user.id)}
                      disabled={user.id === comun?.creator?.id}
                      title={user.id === comun?.creator?.id ? 'Создателя нельзя убрать из модераторов' : 'Убрать модератора'}
                    >
                      Убрать
                    </Button>
                  </div>
                {/each}
              </div>
            </div>
          </div>
        {/if}

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
            {#if normalizedTagCreateValue && !hasExactTagMatch}
              <div class="flex items-center justify-between gap-2 px-3 py-2 bg-slate-50 dark:bg-zinc-900/60">
                <div class="min-w-0 text-sm">
                  <div class="font-medium text-slate-900 dark:text-zinc-100 truncate">
                    Добавить тег #{normalizedTagCreateValue}
                  </div>
                  <div class="text-xs text-slate-500 dark:text-zinc-400">
                    Создаст тег в системе и выберет его для комуны
                  </div>
                </div>
                <Button size="sm" on:click={createTagAndChooseDraft} disabled={settingsTagCreating || settingsSaving}>
                  {settingsTagCreating ? '...' : 'Добавить'}
                </Button>
              </div>
            {/if}
            {#if filteredTagOptions.length}
              {#each filteredTagOptions as tag}
                <div class="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                  <div class="min-w-0">
                    <div class="font-medium text-slate-900 dark:text-zinc-100 truncate">{tag.name}</div>
                    {#if tag.lemma}
                      <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">{tag.lemma}</div>
                    {/if}
                  </div>
                  <Button size="sm" on:click={() => chooseDraftTag(tag)} disabled={settingsTagCreating || settingsSaving}>Выбрать</Button>
                </div>
              {/each}
            {:else}
              <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">
                {normalizedTagCreateValue && !hasExactTagMatch ? 'Можно добавить новый тег выше' : 'Ничего не найдено'}
              </div>
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

      <div class="flex items-center justify-between gap-3 pt-5">
        <div class="text-xs text-slate-500 dark:text-zinc-400">
          {#if settingsHasChanges}
            Есть несохранённые изменения
          {:else}
            Все изменения сохранены
          {/if}
        </div>
        <Button on:click={saveSettings} disabled={!settingsHasChanges || settingsSaving || settingsLogoUploading}>
          {settingsSaving ? 'Сохраняем...' : 'Сохранить'}
        </Button>
      </div>
    </section>
  {/if}
</div>

<svelte:head>
  <title>{pageTitle}</title>
</svelte:head>
