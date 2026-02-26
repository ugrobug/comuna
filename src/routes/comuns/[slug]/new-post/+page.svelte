<script lang="ts">
  import { goto } from '$app/navigation'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Spinner, TextInput, toast } from 'mono-svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import { deserializeEditorModel } from '$lib/util'
  import { buildComunUrl, type BackendComun } from '$lib/api/backend'
  import { createComunPost, refreshSiteUser, siteToken, siteUser } from '$lib/siteAuth'
  import { onMount } from 'svelte'

  export let data

  let comun: BackendComun | null = data.comun ?? null
  let loadingUser = true
  let loadingComunAccess = false
  let authCheckDone = false

  let createTitle = ''
  let createContent = ''
  let createCategoryId = ''
  let createAuthorChoice = ''
  let creating = false
  let createError = ''
  let comunCategories: NonNullable<BackendComun['categories']> = []
  let canCreateInComun = false
  let productTagName = ''
  const SITE_AUTHOR_CHOICE = '__site__'

  type PublishIdentityOption = {
    value: string
    label: string
    kind: 'site' | 'channel'
    username?: string
  }
  let publishIdentityOptions: PublishIdentityOption[] = []

  const isEditorContentEmpty = (value: string) => {
    if (!value || value.trim() === '') return true
    try {
      const parsed = deserializeEditorModel(value)
      return !parsed?.blocks || parsed.blocks.length === 0
    } catch {
      return true
    }
  }

  const refreshComunAccess = async () => {
    if (!comun?.slug || !$siteToken) {
      authCheckDone = true
      return
    }
    loadingComunAccess = true
    try {
      const response = await fetch(buildComunUrl(comun.slug), {
        headers: { Authorization: `Bearer ${$siteToken}` },
      })
      const payload = await response.json().catch(() => ({}))
      if (response.ok && payload?.comun) {
        comun = payload.comun
      }
    } finally {
      loadingComunAccess = false
      authCheckDone = true
    }
  }

  onMount(() => {
    refreshSiteUser()
      .catch(() => null)
      .finally(() => {
        loadingUser = false
        void refreshComunAccess()
      })
  })

  $: comunCategories = comun?.categories ?? []
  $: canCreateInComun = Boolean($siteToken && comun?.can_moderate)
  $: productTagName = comun?.product_tag?.name?.trim() ?? ''
  $: publishIdentityOptions = (() => {
    if (!$siteUser) return [] as PublishIdentityOption[]
    const siteLabelBase = ($siteUser.display_name || '').trim() || `@${$siteUser.username}`
    const items: PublishIdentityOption[] = [
      {
        value: SITE_AUTHOR_CHOICE,
        label: `${siteLabelBase} (аккаунт сайта)`,
        kind: 'site',
        username: $siteUser.username,
      },
    ]
    for (const author of $siteUser.authors ?? []) {
      items.push({
        value: `channel:${author.username}`,
        label: `@${author.username}${author.title ? ` — ${author.title}` : ''}`,
        kind: 'channel',
        username: author.username,
      })
    }
    return items
  })()
  $: if ($siteUser && !createAuthorChoice) {
    createAuthorChoice = $siteUser.authors?.length
      ? `channel:${$siteUser.authors[0]?.username || ''}`
      : SITE_AUTHOR_CHOICE
  }

  const createPost = async () => {
    if (!$siteUser || !comun?.slug) return
    createError = ''

    if (!canCreateInComun) {
      createError = 'Добавлять записи в коммуну могут только модераторы.'
      return
    }
    if (!productTagName) {
      createError = 'Сначала выберите тег продукта в настройках комуны.'
      return
    }
    if (!createTitle.trim()) {
      createError = 'Укажите заголовок поста.'
      return
    }
    if (isEditorContentEmpty(createContent)) {
      createError = 'Текст поста не может быть пустым.'
      return
    }

    creating = true
    try {
      await createComunPost(comun.slug, {
        title: createTitle.trim(),
        content: createContent.trim(),
        author_source: createAuthorChoice === SITE_AUTHOR_CHOICE ? 'site' : undefined,
        author_username:
          createAuthorChoice && createAuthorChoice !== SITE_AUTHOR_CHOICE
            ? createAuthorChoice.replace(/^channel:/, '')
            : undefined,
        comun_category_id: createCategoryId ? Number(createCategoryId) : null,
      })
      toast({
        content: 'Пост опубликован в комуне',
        type: 'success',
      })
      await goto(`/comuns/${comun.slug}`)
    } catch (error) {
      createError = (error as Error)?.message ?? 'Не удалось создать пост'
    } finally {
      creating = false
    }
  }

  const goToLogin = () => {
    if (!comun?.slug) return
    goto(`/account?next=${encodeURIComponent(`/comuns/${comun.slug}/new-post`)}`)
  }
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <div class="flex flex-wrap items-center justify-between gap-3 w-full">
      <div class="min-w-0">
        <h1 class="text-2xl font-bold">Новая запись в комуне</h1>
        <div class="text-sm text-slate-600 dark:text-zinc-400">
          {#if comun?.name}
            {comun.name}
          {:else}
            Комуна
          {/if}
        </div>
      </div>
      {#if comun?.slug}
        <Button color="ghost" on:click={() => goto(`/comuns/${comun.slug}`)}>
          Назад к комуне
        </Button>
      {/if}
    </div>
  </Header>

  <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-6 bg-white/95 dark:bg-zinc-900/85">
    {#if loadingUser || loadingComunAccess}
      <div class="flex items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
        <Spinner size="sm" />
        Загрузка...
      </div>
    {:else if !$siteUser}
      <div class="flex flex-col gap-3">
        <p class="text-sm text-slate-500 dark:text-zinc-400">
          Войдите, чтобы публиковать записи в комуне.
        </p>
        <div>
          <Button on:click={goToLogin}>Войти</Button>
        </div>
      </div>
    {:else if authCheckDone && !canCreateInComun}
      <p class="text-sm text-slate-500 dark:text-zinc-400">
        Добавлять записи в коммуну могут только её модераторы.
      </p>
    {:else}
      <div class="flex flex-col gap-4">
        <div class="rounded-lg border border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-800/40 px-3 py-2 text-sm text-slate-700 dark:text-zinc-300">
          {#if productTagName}
            Тег продукта <span class="font-semibold">#{productTagName}</span> будет добавлен автоматически.
          {:else}
            У этой комуны пока не выбран тег продукта. Укажите его в настройках комуны перед публикацией.
          {/if}
        </div>

        {#if publishIdentityOptions.length > 1}
          <label class="flex flex-col gap-1">
            <span class="text-sm text-slate-700 dark:text-zinc-300">Публиковать от имени</span>
            <select
              bind:value={createAuthorChoice}
              class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            >
              {#each publishIdentityOptions as authorOption}
                <option value={authorOption.value}>{authorOption.label}</option>
              {/each}
            </select>
          </label>
        {/if}

        {#if comunCategories.length}
          <label class="flex flex-col gap-1">
            <span class="text-sm text-slate-700 dark:text-zinc-300">Категория внутри комуны</span>
            <select
              bind:value={createCategoryId}
              class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            >
              <option value="">Без категории</option>
              {#each comunCategories as category}
                <option value={String(category.id)}>{category.name}</option>
              {/each}
            </select>
          </label>
        {/if}

        <TextInput label="Заголовок" bind:value={createTitle} />

        <EditorJS
          bind:value={createContent}
          placeholder="Текст поста"
          enableAutosave={false}
          postId={null}
          showPostSettings={false}
        />

        {#if createError}
          <p class="text-sm text-red-600">{createError}</p>
        {/if}

        <div class="flex flex-wrap gap-2">
          <Button
            color="primary"
            on:click={createPost}
            loading={creating}
            disabled={creating || !productTagName}
          >
            Опубликовать в коммуну
          </Button>
          <Button
            color="ghost"
            on:click={() => {
              createTitle = ''
              createContent = ''
              createCategoryId = ''
              createError = ''
            }}
            disabled={creating}
          >
            Очистить
          </Button>
        </div>
      </div>
    {/if}
  </div>
</div>
