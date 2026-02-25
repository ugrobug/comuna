<script lang="ts">
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import { onMount } from 'svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Modal } from 'mono-svelte'
  import {
    buildThematicFeedsManageUrl,
    type BackendThematicFeed,
  } from '$lib/api/backend'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import { goto } from '$app/navigation'
  import { Plus, Icon } from 'svelte-hero-icons'

  type UserOption = { id: number; username: string }
  type AuthorOption = { id: number; username: string; title?: string | null; rubric?: string | null }
  type TagOption = { id: number; name: string; lemma?: string | null }

  let loading = true
  let saving = false
  let creating = false
  let createModalOpen = false
  let errorMessage = ''
  let successMessage = ''

  let folders: BackendThematicFeed[] = []
  let selectedSlug = ''
  let draft: BackendThematicFeed | null = null

  let userOptions: UserOption[] = []
  let authorOptions: AuthorOption[] = []
  let tagOptions: TagOption[] = []

  let createName = ''
  let createSlug = ''
  let createDescription = ''
  let createSortOrder = 0
  let createIsActive = true
  let createModeratorIds: number[] = []

  const isStaff = () => !!$siteUser?.is_staff

  const resetCreateDraft = () => {
    createName = ''
    createSlug = ''
    createDescription = ''
    createSortOrder = 0
    createIsActive = true
    createModeratorIds = []
  }

  const openCreateModal = () => {
    if (!isStaff()) return
    createModalOpen = true
    errorMessage = ''
    successMessage = ''
  }

  const closeCreateModal = () => {
    createModalOpen = false
  }

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  const cloneFolder = (folder: BackendThematicFeed | null): BackendThematicFeed | null =>
    folder ? JSON.parse(JSON.stringify(folder)) : null

  const setSelectedFolder = (slug: string) => {
    selectedSlug = slug
    draft = cloneFolder(folders.find((item) => item.slug === slug) ?? null)
    successMessage = ''
    errorMessage = ''
  }

  const updateSelectedValues = (event: Event, key: keyof BackendThematicFeed) => {
    if (!draft) return
    const target = event.currentTarget as HTMLSelectElement
    const values = Array.from(target.selectedOptions)
      .map((option) => Number(option.value))
      .filter((value) => Number.isFinite(value) && value > 0)
    ;(draft as any)[key] = values
  }

  const readSelectedIds = (event: Event): number[] => {
    const target = event.currentTarget as HTMLSelectElement
    return Array.from(target.selectedOptions)
      .map((option) => Number(option.value))
      .filter((value) => Number.isFinite(value) && value > 0)
  }

  const loadFolders = async () => {
    loading = true
    errorMessage = ''
    try {
      const response = await fetch(buildThematicFeedsManageUrl(), {
        headers: {
          Authorization: `Bearer ${$siteToken}`,
        },
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось загрузить папки')
      }
      folders = payload.folders ?? []
      userOptions = payload.options?.users ?? []
      authorOptions = payload.options?.authors ?? []
      tagOptions = payload.options?.tags ?? []
      if (folders.length) {
        const nextSlug =
          folders.find((folder) => folder.slug === selectedSlug)?.slug ??
          folders[0].slug
        setSelectedFolder(nextSlug)
      } else {
        selectedSlug = ''
        draft = null
      }
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Ошибка загрузки'
    } finally {
      loading = false
    }
  }

  const createFolder = async () => {
    if (!isStaff()) return
    if (!createName.trim()) {
      errorMessage = 'Введите название папки'
      return
    }
    creating = true
    errorMessage = ''
    successMessage = ''
    try {
      const response = await fetch(buildThematicFeedsManageUrl(), {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          name: createName,
          slug: createSlug,
          description: createDescription,
          sort_order: Number(createSortOrder) || 0,
          is_active: createIsActive,
          moderator_ids: createModeratorIds,
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось создать папку')
      }
      resetCreateDraft()
      await loadFolders()
      if (payload?.folder?.slug) {
        setSelectedFolder(payload.folder.slug)
      }
      createModalOpen = false
      successMessage = 'Папка создана'
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Ошибка создания'
    } finally {
      creating = false
    }
  }

  const saveFolder = async () => {
    if (!draft) return
    saving = true
    errorMessage = ''
    successMessage = ''
    try {
      const body: Record<string, any> = {
        author_ids: draft.author_ids ?? [],
        excluded_author_ids: draft.excluded_author_ids ?? [],
        tag_ids: draft.tag_ids ?? [],
        excluded_tag_ids: draft.excluded_tag_ids ?? [],
      }
      if (isStaff()) {
        body.name = draft.name
        body.slug = draft.slug
        body.description = draft.description ?? ''
        body.sort_order = Number(draft.sort_order ?? 0) || 0
        body.is_active = !!draft.is_active
        body.moderator_ids = draft.moderator_ids ?? []
      }
      const response = await fetch(buildThematicFeedsManageUrl(selectedSlug), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify(body),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось сохранить папку')
      }
      const updated = payload.folder as BackendThematicFeed
      folders = folders.map((folder) => (folder.slug === selectedSlug ? updated : folder))
      if (selectedSlug !== updated.slug) {
        selectedSlug = updated.slug
      }
      draft = cloneFolder(updated)
      successMessage = 'Папка сохранена'
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Ошибка сохранения'
    } finally {
      saving = false
    }
  }

  onMount(async () => {
    if (!$siteToken) {
      loading = false
      return
    }
    await loadFolders()
  })

  $: if (
    browser &&
    isStaff() &&
    $page.url.pathname === '/folders' &&
    $page.url.searchParams.get('create') === '1' &&
    !createModalOpen
  ) {
    createModalOpen = true
    goto('/folders', { replaceState: true, noScroll: true, keepFocus: true })
  }
</script>

<div class="flex flex-col gap-4 max-w-full min-w-0">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <Header pageHeader>Папки</Header>
    {#if $siteUser?.is_staff}
      <Button on:click={openCreateModal}>
        <span class="inline-flex items-center gap-2">
          <Icon src={Plus} size="16" mini />
          <span>Создать папку</span>
        </span>
      </Button>
    {/if}
  </div>

  {#if !$siteUser}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 text-sm text-slate-600 dark:text-zinc-300">
      Нужна авторизация. Войдите, чтобы управлять папками.
      <div class="mt-3">
        <Button on:click={() => goto('/account?next=/folders')}>Войти</Button>
      </div>
    </div>
  {:else if loading}
    <div class="text-sm text-slate-500 dark:text-zinc-400">Загружаем папки...</div>
  {:else if errorMessage && !folders.length && !isStaff()}
    <div class="rounded-2xl border border-rose-200 dark:border-rose-900 bg-rose-50/70 dark:bg-rose-950/20 p-4 text-sm text-rose-700 dark:text-rose-300">
      {errorMessage}
    </div>
  {:else}
    {#if errorMessage}
      <div class="rounded-2xl border border-rose-200 dark:border-rose-900 bg-rose-50/70 dark:bg-rose-950/20 p-4 text-sm text-rose-700 dark:text-rose-300">
        {errorMessage}
      </div>
    {/if}
    {#if successMessage}
      <div class="rounded-2xl border border-emerald-200 dark:border-emerald-900 bg-emerald-50/70 dark:bg-emerald-950/20 p-4 text-sm text-emerald-700 dark:text-emerald-300">
        {successMessage}
      </div>
    {/if}

    <Modal bind:open={createModalOpen} on:close={closeCreateModal}>
      <div class="w-full max-w-[36rem] flex flex-col gap-4">
        <div>
          <h2 class="text-xl font-semibold text-slate-900 dark:text-zinc-100">Создать папку</h2>
          <p class="mt-1 text-sm text-slate-500 dark:text-zinc-400">
            Настройте базовые параметры и назначьте модераторов. Авторов и теги можно потом редактировать на странице папки.
          </p>
        </div>

        {#if errorMessage && createModalOpen}
          <div class="rounded-xl border border-rose-200 dark:border-rose-900 bg-rose-50/70 dark:bg-rose-950/20 p-3 text-sm text-rose-700 dark:text-rose-300">
            {errorMessage}
          </div>
        {/if}

        <div class="grid gap-3">
          <input class="px-3 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950" bind:value={createName} placeholder="Название" />
          <input class="px-3 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950" bind:value={createSlug} placeholder="slug (необязательно)" />
          <textarea class="px-3 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 min-h-[80px]" bind:value={createDescription} placeholder="Описание" />
          <div class="grid grid-cols-2 gap-3">
            <label class="flex flex-col gap-1 text-sm">
              <span>Порядок</span>
              <input type="number" class="px-3 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950" bind:value={createSortOrder} />
            </label>
            <label class="flex items-center gap-2 text-sm pt-6">
              <input type="checkbox" bind:checked={createIsActive} />
              <span>Активна</span>
            </label>
          </div>
          <label class="flex flex-col gap-1 text-sm">
            <span>Модераторы</span>
            <select multiple size="8" class="px-2 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950" on:change={(e) => {
              createModeratorIds = readSelectedIds(e)
            }}>
              {#each userOptions as user}
                <option value={user.id} selected={createModeratorIds.includes(user.id)}>{user.username}</option>
              {/each}
            </select>
          </label>
        </div>

        <div class="flex justify-end gap-2">
          <Button color="ghost" on:click={closeCreateModal}>Отмена</Button>
          <Button disabled={creating} on:click={createFolder}>
            {creating ? 'Создаем...' : 'Создать папку'}
          </Button>
        </div>
      </div>
    </Modal>

    <div class="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
      <div class="flex flex-col gap-4">
        <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 flex flex-col gap-2">
          <h2 class="text-base font-semibold text-slate-900 dark:text-zinc-100">Список папок</h2>
          {#if folders.length}
            <div class="flex flex-col gap-1">
              {#each folders as folder}
                <button
                  type="button"
                  class="text-left rounded-xl px-3 py-2 border transition-colors {selectedSlug === folder.slug ? 'border-blue-300 dark:border-blue-700 bg-blue-50/70 dark:bg-blue-950/20' : 'border-slate-200 dark:border-zinc-800 hover:bg-slate-50 dark:hover:bg-zinc-800/60'}"
                  on:click={() => setSelectedFolder(folder.slug)}
                >
                  <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">{folder.name}</div>
                  <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">
                    {folder.authors_count ?? 0} авторов · {folder.tags_count ?? 0} тегов
                  </div>
                </button>
              {/each}
            </div>
          {:else}
            <div class="text-sm text-slate-500 dark:text-zinc-400">Пока нет папок.</div>
          {/if}
        </section>
      </div>

      <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 flex flex-col gap-4 min-w-0">
        {#if !draft}
          <div class="text-sm text-slate-500 dark:text-zinc-400">Выберите папку слева.</div>
        {:else}
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-base font-semibold text-slate-900 dark:text-zinc-100 truncate">
              Настройка папки: {draft.name}
            </h2>
            <Button disabled={saving} on:click={saveFolder}>
              {saving ? 'Сохраняем...' : 'Сохранить'}
            </Button>
          </div>

          {#if isStaff()}
            <div class="grid gap-3 md:grid-cols-2">
              <label class="flex flex-col gap-1 text-sm min-w-0">
                <span>Название</span>
                <input class="px-3 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950" bind:value={draft.name} />
              </label>
              <label class="flex flex-col gap-1 text-sm min-w-0">
                <span>Slug</span>
                <input class="px-3 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950" bind:value={draft.slug} />
              </label>
              <label class="flex flex-col gap-1 text-sm md:col-span-2">
                <span>Описание</span>
                <textarea class="px-3 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 min-h-[80px]" bind:value={draft.description} />
              </label>
              <label class="flex flex-col gap-1 text-sm">
                <span>Порядок</span>
                <input type="number" class="px-3 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950" bind:value={draft.sort_order} />
              </label>
              <label class="flex items-center gap-2 text-sm pt-6">
                <input type="checkbox" bind:checked={draft.is_active} />
                <span>Активна</span>
              </label>
              <label class="flex flex-col gap-1 text-sm md:col-span-2">
                <span>Модераторы</span>
                <select
                  multiple
                  size="6"
                  class="px-2 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950"
                  on:change={(e) => updateSelectedValues(e, 'moderator_ids')}
                >
                  {#each userOptions as user}
                    <option value={user.id} selected={(draft.moderator_ids ?? []).includes(user.id)}>
                      {user.username}
                    </option>
                  {/each}
                </select>
              </label>
            </div>
          {/if}

          <div class="grid gap-4 xl:grid-cols-2">
            <label class="flex flex-col gap-1 text-sm min-w-0">
              <span>Авторы</span>
              <select
                multiple
                size="12"
                class="px-2 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950"
                on:change={(e) => updateSelectedValues(e, 'author_ids')}
              >
                {#each authorOptions as author}
                  <option value={author.id} selected={(draft.author_ids ?? []).includes(author.id)}>
                    @{author.username}{author.rubric ? ` · ${author.rubric}` : ''}
                  </option>
                {/each}
              </select>
            </label>

            <label class="flex flex-col gap-1 text-sm min-w-0">
              <span>Исключенные авторы</span>
              <select
                multiple
                size="12"
                class="px-2 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950"
                on:change={(e) => updateSelectedValues(e, 'excluded_author_ids')}
              >
                {#each authorOptions as author}
                  <option value={author.id} selected={(draft.excluded_author_ids ?? []).includes(author.id)}>
                    @{author.username}{author.rubric ? ` · ${author.rubric}` : ''}
                  </option>
                {/each}
              </select>
            </label>

            <label class="flex flex-col gap-1 text-sm min-w-0">
              <span>Теги</span>
              <select
                multiple
                size="12"
                class="px-2 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950"
                on:change={(e) => updateSelectedValues(e, 'tag_ids')}
              >
                {#each tagOptions as tag}
                  <option value={tag.id} selected={(draft.tag_ids ?? []).includes(tag.id)}>
                    {tag.name}
                  </option>
                {/each}
              </select>
            </label>

            <label class="flex flex-col gap-1 text-sm min-w-0">
              <span>Исключенные теги</span>
              <select
                multiple
                size="12"
                class="px-2 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950"
                on:change={(e) => updateSelectedValues(e, 'excluded_tag_ids')}
              >
                {#each tagOptions as tag}
                  <option value={tag.id} selected={(draft.excluded_tag_ids ?? []).includes(tag.id)}>
                    {tag.name}
                  </option>
                {/each}
              </select>
            </label>
          </div>
        {/if}
      </section>
    </div>
  {/if}
</div>
