<script lang="ts">
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Spinner, TextInput, toast } from 'mono-svelte'
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
  import PostTemplateFields from '$lib/components/site/post-templates/PostTemplateFields.svelte'
  import {
    buildPostTemplatePayload,
    createEmptyMovieReviewTemplateData,
    normalizeAllowedPostTemplateTypes,
    normalizeTemplateEditorBlockSettings,
    resolveEnabledTemplateEditorBlockTypes,
    type MovieReviewTemplateData,
    type PostTemplateType,
    type TemplateEditorBlockSettings,
  } from '$lib/postTemplates'

  let loadingUser = true
  let createTitle = ''
  let createContent = ''
  let createTags = ''
  let createAuthor = ''
  let createRubric = ''
  let creating = false
  let createError = ''
  let rubricsLoading = false
  type RubricOption = {
    name: string
    slug: string
    icon_url?: string | null
    icon_thumb_url?: string | null
    allowed_template_types?: string[]
  }
  let rubrics: RubricOption[] = []
  let rubricMenuOpen = false
  let rubricMenuRef: HTMLDivElement | null = null
  let selectedRubric: RubricOption | undefined
  let publishIdentityOptions: PublishIdentityOption[] = []
  let selectedIdentity: PublishIdentityOption | undefined
  let selectedChannelIdentity: PublishIdentityOption | undefined
  const SITE_AUTHOR_CHOICE = '__site__'
  let createTemplateType: '' | PostTemplateType = ''
  let createMovieReviewData: MovieReviewTemplateData = createEmptyMovieReviewTemplateData()
  let templateEditorBlockSettings: TemplateEditorBlockSettings = {}

  type PublishIdentityOption = {
    value: string
    label: string
    kind: 'site' | 'channel'
    username?: string
    rubric_slug?: string | null
  }

  $: selectedRubric = rubrics.find((rubric) => rubric.slug === createRubric)
  $: publishIdentityOptions = (() => {
    if (!$siteUser) return [] as PublishIdentityOption[]
    const siteLabelBase = ($siteUser.display_name || '').trim() || `@${$siteUser.username}`
    const items: PublishIdentityOption[] = [
      {
        value: SITE_AUTHOR_CHOICE,
        label: siteLabelBase,
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
        rubric_slug: author.rubric_slug ?? null,
      })
    }
    return items
  })()
  $: selectedIdentity = publishIdentityOptions.find((item) => item.value === createAuthor)
  $: selectedChannelIdentity = selectedIdentity?.kind === 'channel' ? selectedIdentity : undefined
  $: editorEnabledTemplateBlockTypes = resolveEnabledTemplateEditorBlockTypes(
    createTemplateType,
    templateEditorBlockSettings
  )
  $: editorTemplateBlocksKey = `${createTemplateType || 'basic'}:${editorEnabledTemplateBlockTypes.join(',')}`

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
      rubrics = Array.isArray(data?.rubrics)
        ? data.rubrics.map((rubric: any) => ({
            ...rubric,
            allowed_template_types: normalizeAllowedPostTemplateTypes(rubric?.allowed_template_types),
          }))
        : []
      templateEditorBlockSettings = normalizeTemplateEditorBlockSettings(
        data?.template_editor_blocks_by_template
      )
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

  $: if ($siteUser && !createAuthor) {
    createAuthor = $siteUser.authors?.length
      ? `channel:${$siteUser.authors[0]?.username || ''}`
      : SITE_AUTHOR_CHOICE
  }
  $: if (!createRubric && selectedChannelIdentity?.rubric_slug) {
    const authorRubric = selectedChannelIdentity.rubric_slug || ''
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
    if (publishIdentityOptions.length > 1 && !createAuthor) {
      createError = 'Выберите автора публикации.'
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
      const template = buildPostTemplatePayload(
        createTemplateType,
        createMovieReviewData
      )
      await createUserPost({
        title: createTitle.trim(),
        content: createContent.trim(),
        author_source: createAuthor === SITE_AUTHOR_CHOICE ? 'site' : undefined,
        author_username:
          createAuthor && createAuthor !== SITE_AUTHOR_CHOICE
            ? createAuthor.replace(/^channel:/, '')
            : undefined,
        rubric_slug: createRubric || undefined,
        tags: tags.length ? tags : undefined,
        template: template ?? undefined,
      })
      createTitle = ''
      createContent = ''
      createTags = ''
      createTemplateType = ''
      createMovieReviewData = createEmptyMovieReviewTemplateData()
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
        <div
          class={`grid grid-cols-1 gap-4 items-start ${
            publishIdentityOptions.length > 1 ? 'md:grid-cols-2' : ''
          }`}
        >
          {#if publishIdentityOptions.length > 1}
            <label class="flex flex-col gap-1 w-full">
              <span class="text-sm text-slate-700 dark:text-zinc-300">Публиковать от имени</span>
              <select
                bind:value={createAuthor}
                class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
              >
                {#each publishIdentityOptions as authorOption}
                  <option value={authorOption.value}>{authorOption.label}</option>
                {/each}
              </select>
            </label>
          {/if}

          {#if rubricsLoading}
            <div class="flex min-h-[42px] items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
              <Spinner size="sm" />
              Загрузка рубрик...
            </div>
          {:else}
            <div class="relative w-full" bind:this={rubricMenuRef}>
              <button
                type="button"
                class="w-full min-w-0 max-w-full rounded-lg border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-2 text-left shadow-sm flex items-start justify-between gap-3"
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
        </div>
        <TextInput label="Заголовок" bind:value={createTitle} />
        <PostTemplateFields
          bind:templateType={createTemplateType}
          bind:movieReviewData={createMovieReviewData}
          allowedTemplateTypes={selectedRubric?.allowed_template_types}
        />
        {#key `editor-template-${editorTemplateBlocksKey}`}
          <EditorJS
            bind:value={createContent}
            placeholder="Текст поста"
            postTemplateType={createTemplateType}
            enabledTemplateEditorBlockTypes={editorEnabledTemplateBlockTypes}
            enableAutosave={false}
            postId={null}
            showPostSettings={false}
          />
        {/key}
        <TextInput label="Теги (через запятую)" bind:value={createTags} />
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
              createTemplateType = ''
              createMovieReviewData = createEmptyMovieReviewTemplateData()
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
