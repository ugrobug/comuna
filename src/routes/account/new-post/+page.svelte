<script lang="ts">
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Spinner, TextInput, Select, toast } from 'mono-svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import { onMount } from 'svelte'
  import { deserializeEditorModel } from '$lib/util'
  import {
    createUserPost,
    refreshSiteUser,
    siteToken,
    siteUser,
  } from '$lib/siteAuth'
  import { buildRubricsUrl } from '$lib/api/backend'

  let loadingUser = true
  let createTitle = ''
  let createContent = ''
  let createTags = ''
  let createAuthor = ''
  let createRubric = ''
  let creating = false
  let createError = ''
  let rubricsLoading = false
  let rubrics: Array<{ name: string; slug: string; icon_url?: string | null; icon_thumb_url?: string | null }> = []
  let rubricMenuOpen = false
  let rubricMenuRef: HTMLDivElement | null = null
  let selectedRubric: { name: string; slug: string; icon_url?: string | null; icon_thumb_url?: string | null } | undefined

  $: selectedRubric = rubrics.find((rubric) => rubric.slug === createRubric)

  const isEditorContentEmpty = (value: string) => {
    if (!value || value.trim() === '') return true
    try {
      const data = deserializeEditorModel(value)
      return !data?.blocks || data.blocks.length === 0
    } catch {
      return true
    }
  }

  const loadRubrics = async () => {
    if (rubricsLoading) return
    rubricsLoading = true
    const headers: Record<string, string> = {}
    if ($siteToken) {
      headers.Authorization = `Bearer ${$siteToken}`
    }
    try {
      const response = await fetch(buildRubricsUrl({ includeHidden: true }), {
        headers,
      })
      const data = await response.json()
      rubrics = data?.rubrics ?? []
      if (!createRubric && rubrics.length === 1) {
        createRubric = rubrics[0].slug
      }
    } catch {
      rubrics = []
    } finally {
      rubricsLoading = false
    }
  }

  onMount(() => {
    refreshSiteUser().finally(() => {
      loadingUser = false
      loadRubrics()
    })

    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!rubricMenuOpen || !rubricMenuRef) return
      const target = event.target as Node | null
      if (target && !rubricMenuRef.contains(target)) {
        rubricMenuOpen = false
      }
    }
    document.addEventListener('click', closeOnOutsideClick)
    return () => {
      document.removeEventListener('click', closeOnOutsideClick)
    }
  })

  $: if ($siteUser?.authors?.length && !createAuthor) {
    createAuthor = $siteUser.authors[0]?.username || ''
  }
  $: if (!createRubric && $siteUser?.authors?.length === 1) {
    const authorRubric = $siteUser.authors[0]?.rubric_slug || ''
    if (authorRubric) createRubric = authorRubric
  }
  $: if (!createRubric && createAuthor && $siteUser?.authors?.length) {
    const matched = $siteUser.authors.find((author) => author.username === createAuthor)
    const authorRubric = matched?.rubric_slug || ''
    if (authorRubric) createRubric = authorRubric
  }

  const createPost = async () => {
    if (!$siteUser) return
    createError = ''
    if (!createTitle.trim()) {
      createError = 'Укажите заголовок поста.'
      return
    }
    if (isEditorContentEmpty(createContent)) {
      createError = 'Текст поста не может быть пустым.'
      return
    }
    if ($siteUser.authors.length > 1 && !createAuthor) {
      createError = 'Выберите канал для публикации.'
      return
    }
    if (!createRubric) {
      createError = 'Выберите рубрику для публикации.'
      return
    }
    creating = true
    try {
      const tags = createTags
        .split(',')
        .map((tag) => tag.trim())
        .filter((tag) => tag.length > 0)
      await createUserPost({
        title: createTitle.trim(),
        content: createContent.trim(),
        author_username: createAuthor || undefined,
        rubric_slug: createRubric || undefined,
        tags: tags.length ? tags : undefined,
      })
      createTitle = ''
      createContent = ''
      createTags = ''
      toast({
        content:
          'Ваш пост опубликован! Не забудьте поделиться ссылкой на него в социальных сетях',
        type: 'success',
      })
    } catch (err) {
      createError = (err as Error)?.message ?? 'Не удалось создать пост'
    } finally {
      creating = false
    }
  }

  const selectRubric = (slug: string) => {
    createRubric = slug
    rubricMenuOpen = false
  }
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Новый пост</h1>
  </Header>

  {#if loadingUser}
    <div class="flex items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
      <Spinner size="sm" />
      Загрузка...
    </div>
  {:else if !$siteUser}
    <p class="text-sm text-slate-500 dark:text-zinc-400">
      Войдите, чтобы создавать посты.
    </p>
  {:else}
    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-6">
      {#if !$siteUser.authors.length}
        <p class="text-sm text-slate-500 dark:text-zinc-400">
          Канал не привязан — пост будет опубликован от вашего аккаунта.
        </p>
      {/if}
      <div class="flex flex-col gap-4">
        {#if $siteUser.authors.length > 1}
          <Select bind:value={createAuthor} class="max-w-xs">
            <option value="" disabled>Выберите канал</option>
            {#each $siteUser.authors as author}
              <option value={author.username}>@{author.username}</option>
            {/each}
          </Select>
        {/if}
        {#if rubricsLoading}
          <div class="flex items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
            <Spinner size="sm" />
            Загрузка рубрик...
          </div>
        {:else}
          <div class="relative w-full" bind:this={rubricMenuRef}>
            <button
              type="button"
              class="w-full min-w-0 sm:min-w-[22rem] max-w-full rounded-lg border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-2 text-left shadow-sm flex items-start justify-between gap-3"
              aria-haspopup="listbox"
              aria-expanded={rubricMenuOpen}
              on:click={() => (rubricMenuOpen = !rubricMenuOpen)}
            >
              <div class="flex items-start gap-2 min-w-0">
                <div class="h-7 w-7 rounded-full border border-slate-200 dark:border-zinc-700 bg-slate-100 dark:bg-zinc-800 overflow-hidden flex items-center justify-center text-xs font-semibold text-slate-500 dark:text-zinc-400">
                  {#if selectedRubric?.icon_thumb_url || selectedRubric?.icon_url}
                    <img
                      src={selectedRubric.icon_thumb_url ?? selectedRubric.icon_url}
                      alt={selectedRubric.name}
                      class="h-full w-full object-cover"
                    />
                  {:else if selectedRubric?.name}
                    {selectedRubric.name[0]}
                  {:else}
                    #
                  {/if}
                </div>
                <span class="text-sm text-slate-700 dark:text-zinc-200 whitespace-normal break-words">
                  {#if selectedRubric}
                    {selectedRubric.name}
                  {:else}
                    Выберите рубрику
                  {/if}
                </span>
              </div>
              <svg
                class="h-4 w-4 text-slate-500 dark:text-zinc-400 flex-shrink-0"
                viewBox="0 0 20 20"
                fill="currentColor"
                aria-hidden="true"
              >
                <path
                  fill-rule="evenodd"
                  d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.24 4.5a.75.75 0 01-1.08 0l-4.24-4.5a.75.75 0 01.02-1.06z"
                  clip-rule="evenodd"
                />
              </svg>
            </button>

            {#if rubricMenuOpen}
              <div
                class="absolute z-20 mt-2 w-full rounded-lg border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-lg max-h-72 overflow-auto"
                role="listbox"
              >
                {#each rubrics as rubric}
                  <button
                    type="button"
                    class={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50 dark:hover:bg-zinc-800 ${
                      createRubric === rubric.slug ? 'bg-slate-100 dark:bg-zinc-800' : ''
                    }`}
                    on:click={() => selectRubric(rubric.slug)}
                  >
                    <div class="h-7 w-7 rounded-full border border-slate-200 dark:border-zinc-700 bg-slate-100 dark:bg-zinc-800 overflow-hidden flex items-center justify-center text-xs font-semibold text-slate-500 dark:text-zinc-400 flex-shrink-0">
                      {#if rubric.icon_thumb_url || rubric.icon_url}
                        <img
                          src={rubric.icon_thumb_url ?? rubric.icon_url}
                          alt={rubric.name}
                          class="h-full w-full object-cover"
                        />
                      {:else}
                        {rubric.name?.[0] ?? 'R'}
                      {/if}
                    </div>
                    <span class="flex-1 whitespace-normal text-slate-700 dark:text-zinc-200">
                      {rubric.name}
                    </span>
                  </button>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
        <TextInput label="Заголовок" bind:value={createTitle} />
        <TextInput label="Теги (через запятую)" bind:value={createTags} />
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
          <Button color="primary" on:click={createPost} loading={creating} disabled={creating}>
            Опубликовать
          </Button>
          <Button
            color="ghost"
            on:click={() => {
              createTitle = ''
              createContent = ''
              createTags = ''
              createError = ''
            }}
            disabled={creating}
          >
            Очистить
          </Button>
        </div>
      </div>
    </div>
  {/if}
</div>
