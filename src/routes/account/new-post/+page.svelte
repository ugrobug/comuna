<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Spinner, TextInput, toast } from 'mono-svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import { onDestroy, onMount, tick } from 'svelte'
  import { deserializeEditorModel } from '$lib/util'
  import {
    createUserPost,
    refreshSiteUser,
    siteToken,
    siteUser,
    updateUserPost,
  } from '$lib/siteAuth'
  import { buildBackendPostPath, buildRubricsUrl } from '$lib/api/backend'
  import PostTemplateFields from '$lib/components/site/post-templates/PostTemplateFields.svelte'
  import {
    POST_TEMPLATE_TYPE_OPTIONS,
    buildPostTemplatePayload,
    createEmptyMusicReleaseTemplateData,
    createEmptyMovieReviewTemplateData,
    createEmptyPostVotePollTemplateData,
    normalizeAllowedPostTemplateTypes,
    normalizeTemplateEditorBlockSettings,
    resolveEnabledTemplateEditorBlockTypes,
    type MusicReleaseTemplateData,
    type MovieReviewTemplateData,
    type PostVotePollTemplateData,
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
  let draftError = ''
  let draftCreating = false
  let draftId: number | null = null
  let rubricsLoading = false
  let autosavePrimed = false
  let initialFormSnapshot = ''
  let lastSavedFormSnapshot = ''
  let lastObservedFormSnapshot = ''
  let currentFormSnapshot = ''
  let autosaveTimeout: ReturnType<typeof setTimeout> | null = null
  type RubricOption = {
    name: string
    slug: string
    icon_url?: string | null
    icon_thumb_url?: string | null
    allowed_template_types?: string[]
  }
  let rubrics: RubricOption[] = []
  let rubricMenuOpen = false
  let rubricSearchQuery = ''
  let rubricMenuRef: HTMLDivElement | null = null
  let filteredRubrics: RubricOption[] = []
  let identityMenuOpen = false
  let identityMenuRef: HTMLDivElement | null = null
  let templateMenuOpen = false
  let templateMenuRef: HTMLDivElement | null = null
  let hasTemplateTypeChoice = false
  let allowedTemplateTypeSet = new Set<string>()
  let availableTemplateTypeOptions = POST_TEMPLATE_TYPE_OPTIONS
  let selectedTemplateOption = POST_TEMPLATE_TYPE_OPTIONS[0]
  let selectedRubric: RubricOption | undefined
  let publishIdentityOptions: PublishIdentityOption[] = []
  let selectedIdentity: PublishIdentityOption | undefined
  let selectedChannelIdentity: PublishIdentityOption | undefined
  const SITE_AUTHOR_CHOICE = '__site__'
  const LOCAL_DRAFT_STORAGE_KEY = 'comuna.site.new-post.buffer.v1'
  let createTemplateType: '' | PostTemplateType = ''
  let createMovieReviewData: MovieReviewTemplateData = createEmptyMovieReviewTemplateData()
  let createPostVotePollData: PostVotePollTemplateData = createEmptyPostVotePollTemplateData()
  let createMusicReleaseData: MusicReleaseTemplateData = createEmptyMusicReleaseTemplateData()
  let templateEditorBlockSettings: TemplateEditorBlockSettings = {}
  let firstDraftChangeAt: number | null = null
  let firstDraftAutosaveCompleted = false
  let draftSavedNoticeVisible = false
  let draftSavedNoticeTimer: ReturnType<typeof setTimeout> | null = null
  let draftSavedNoticeHideTimer: ReturnType<typeof setTimeout> | null = null

  const DRAFT_NOTICE_DELAY_MS = 10_000
  const DRAFT_NOTICE_VISIBLE_MS = 5_000

  type PublishIdentityOption = {
    value: string
    label: string
    shortLabel: string
    kind: 'site' | 'channel'
    username?: string
    title?: string | null
    avatar_url?: string | null
    rubric_slug?: string | null
  }

  $: selectedRubric = rubrics.find((rubric) => rubric.slug === createRubric)
  $: filteredRubrics = (() => {
    const query = rubricSearchQuery.trim().toLowerCase()
    if (!query) return rubrics
    return rubrics.filter((rubric) => {
      const name = (rubric.name || '').toLowerCase()
      const slug = (rubric.slug || '').toLowerCase()
      return name.includes(query) || slug.includes(query)
    })
  })()
  $: publishIdentityOptions = (() => {
    if (!$siteUser) return [] as PublishIdentityOption[]
    const siteLabelBase = ($siteUser.display_name || '').trim() || `@${$siteUser.username}`
    const items: PublishIdentityOption[] = [
      {
        value: SITE_AUTHOR_CHOICE,
        label: siteLabelBase,
        shortLabel: siteLabelBase,
        kind: 'site',
        username: $siteUser.username,
        avatar_url: $siteUser.avatar_url ?? null,
      },
    ]
    for (const author of $siteUser.authors ?? []) {
      items.push({
        value: `channel:${author.username}`,
        label: `@${author.username}${author.title ? ` — ${author.title}` : ''}`,
        shortLabel: author.title?.trim() || `@${author.username}`,
        kind: 'channel',
        username: author.username,
        title: author.title ?? null,
        avatar_url: author.avatar_url ?? null,
        rubric_slug: author.rubric_slug ?? null,
      })
    }
    return items
  })()
  $: selectedIdentity = publishIdentityOptions.find((item) => item.value === createAuthor)
  $: selectedChannelIdentity = selectedIdentity?.kind === 'channel' ? selectedIdentity : undefined
  $: allowedTemplateTypeSet = new Set(
    normalizeAllowedPostTemplateTypes(selectedRubric?.allowed_template_types)
  )
  $: availableTemplateTypeOptions = POST_TEMPLATE_TYPE_OPTIONS.filter((option) =>
    option.value ? allowedTemplateTypeSet.has(option.value) : allowedTemplateTypeSet.has('basic')
  )
  $: hasTemplateTypeChoice = availableTemplateTypeOptions.length > 1
  $: selectedTemplateOption =
    availableTemplateTypeOptions.find((option) => option.value === createTemplateType) ??
    availableTemplateTypeOptions[0] ??
    POST_TEMPLATE_TYPE_OPTIONS[0]
  $: profileDraftsPath = $siteUser?.id ? `/id${$siteUser.id}` : '/settings'
  $: if (!availableTemplateTypeOptions.some((option) => option.value === createTemplateType)) {
    createTemplateType = availableTemplateTypeOptions[0]?.value ?? ''
  }
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

  const buildTags = () =>
    createTags
      .split(',')
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0)

  const buildTemplate = () =>
    buildPostTemplatePayload(
      createTemplateType,
      createMovieReviewData,
      createPostVotePollData,
      createMusicReleaseData
    )

  const buildDraftPayload = () => {
    const tags = buildTags()
    const template = buildTemplate()
    return {
      title: createTitle.trim(),
      content: createContent.trim(),
      author_source: createAuthor === SITE_AUTHOR_CHOICE ? ('site' as const) : undefined,
      author_username:
        createAuthor && createAuthor !== SITE_AUTHOR_CHOICE
          ? createAuthor.replace(/^channel:/, '')
          : undefined,
      rubric_slug: createRubric || undefined,
      tags: tags.length ? tags : undefined,
      template: template ?? undefined,
    }
  }

  const buildLocalDraftState = () => ({
    title: createTitle,
    content: createContent,
    tags: createTags,
    author: createAuthor,
    rubric: createRubric,
    templateType: createTemplateType,
    movieReviewData: createMovieReviewData,
    postVotePollData: createPostVotePollData,
    musicReleaseData: createMusicReleaseData,
  })

  const localDraftStorageKey = () =>
    $siteUser ? `${LOCAL_DRAFT_STORAGE_KEY}:${$siteUser.id}` : null

  const clearLocalDraftBuffer = () => {
    if (!browser) return
    const key = localDraftStorageKey()
    if (!key) return
    localStorage.removeItem(key)
  }

  const persistLocalDraftBuffer = () => {
    if (!browser) return
    const key = localDraftStorageKey()
    if (!key) return
    localStorage.setItem(
      key,
      JSON.stringify({
        saved_at: new Date().toISOString(),
        draft_id: draftId,
        first_change_at: firstDraftChangeAt,
        ...buildLocalDraftState(),
      })
    )
  }

  const restoreLocalDraftBuffer = () => {
    if (!browser) return false
    const key = localDraftStorageKey()
    if (!key) return false
    const raw = localStorage.getItem(key)
    if (!raw) return false
    try {
      const parsed = JSON.parse(raw)
      const nextAuthor = String(parsed?.author || '')
      const nextRubric = String(parsed?.rubric || '')
      const nextTemplateType = String(parsed?.templateType || '') as '' | PostTemplateType
      const nextDraftId = Number(parsed?.draft_id ?? 0)
      const nextFirstChangeAt = Number(parsed?.first_change_at ?? 0)
      const authorExists =
        !nextAuthor || publishIdentityOptions.some((item) => item.value === nextAuthor)
      const rubricExists = !nextRubric || rubrics.some((item) => item.slug === nextRubric)
      createTitle = String(parsed?.title || '')
      createContent = String(parsed?.content || '')
      createTags = String(parsed?.tags || '')
      createAuthor = authorExists ? nextAuthor : createAuthor
      createRubric = rubricExists ? nextRubric : createRubric
      createTemplateType =
        nextTemplateType === 'movie_review' ||
        nextTemplateType === 'post_vote_poll' ||
        nextTemplateType === 'music_release'
          ? nextTemplateType
          : ''
      createMovieReviewData = parsed?.movieReviewData ?? createEmptyMovieReviewTemplateData()
      createPostVotePollData =
        parsed?.postVotePollData ?? createEmptyPostVotePollTemplateData()
      createMusicReleaseData =
        parsed?.musicReleaseData ?? createEmptyMusicReleaseTemplateData()
      draftId = Number.isFinite(nextDraftId) && nextDraftId > 0 ? nextDraftId : null
      firstDraftChangeAt =
        Number.isFinite(nextFirstChangeAt) && nextFirstChangeAt > 0 ? nextFirstChangeAt : null
      return true
    } catch {
      localStorage.removeItem(key)
      return false
    }
  }

  const clearAutosaveTimeout = () => {
    if (!autosaveTimeout) return
    clearTimeout(autosaveTimeout)
    autosaveTimeout = null
  }

  const clearDraftSavedNoticeTimer = () => {
    if (!draftSavedNoticeTimer) return
    clearTimeout(draftSavedNoticeTimer)
    draftSavedNoticeTimer = null
  }

  const clearDraftSavedNoticeHideTimer = () => {
    if (!draftSavedNoticeHideTimer) return
    clearTimeout(draftSavedNoticeHideTimer)
    draftSavedNoticeHideTimer = null
  }

  const clearDraftSavedNotice = () => {
    draftSavedNoticeVisible = false
    clearDraftSavedNoticeTimer()
    clearDraftSavedNoticeHideTimer()
  }

  const scheduleDraftSavedNotice = () => {
    if (!draftId || draftSavedNoticeVisible) return
    clearDraftSavedNoticeTimer()
    clearDraftSavedNoticeHideTimer()
    const elapsed = Date.now() - (firstDraftChangeAt ?? Date.now())
    const delay = Math.max(0, DRAFT_NOTICE_DELAY_MS - elapsed)
    draftSavedNoticeTimer = setTimeout(() => {
      draftSavedNoticeVisible = true
      draftSavedNoticeHideTimer = setTimeout(() => {
        draftSavedNoticeVisible = false
      }, DRAFT_NOTICE_VISIBLE_MS)
    }, delay)
  }

  const getAvatarFallback = (identity: PublishIdentityOption | undefined) => {
    const source = identity?.shortLabel?.trim() || identity?.username?.trim() || 'A'
    return source.charAt(0).toUpperCase()
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
        cache: 'no-store',
      })
      const data = await response.json()
      rubrics = Array.isArray(data?.rubrics)
        ? data.rubrics.map((rubric: any) => ({
            ...rubric,
            allowed_template_types: normalizeAllowedPostTemplateTypes(
              rubric?.allowed_template_types ?? rubric?.allowed_post_templates
            ),
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

  const queueDraftSave = () => {
    if (!autosavePrimed || !$siteUser || creating || draftCreating) return
    if (currentFormSnapshot === lastSavedFormSnapshot) return
    clearAutosaveTimeout()
    draftError = ''

    autosaveTimeout = setTimeout(async () => {
      if (currentFormSnapshot === lastSavedFormSnapshot) return
      draftCreating = true
      const sentSnapshot = currentFormSnapshot
      let needsAnotherSave = false
      try {
        const draft = draftId
          ? await updateUserPost(draftId, {
              ...buildDraftPayload(),
              is_draft: true,
            })
          : await createUserPost({
              ...buildDraftPayload(),
              is_draft: true,
            })
        const isFirstSave = !draftId
        draftId = draft.id
        lastSavedFormSnapshot = sentSnapshot
        persistLocalDraftBuffer()
        const latestSnapshot = JSON.stringify(buildLocalDraftState())
        needsAnotherSave = latestSnapshot !== sentSnapshot
        if (isFirstSave || !firstDraftAutosaveCompleted) {
          firstDraftAutosaveCompleted = true
          scheduleDraftSavedNotice()
        }
      } catch (error) {
        draftError = (error as Error)?.message ?? 'Не удалось сохранить черновик'
      } finally {
        draftCreating = false
        if (needsAnotherSave) {
          queueDraftSave()
        }
      }
    }, 900)
  }

  const resetForm = () => {
    clearAutosaveTimeout()
    if (!draftId) {
      firstDraftChangeAt = null
      firstDraftAutosaveCompleted = false
      clearDraftSavedNotice()
    }
    createTitle = ''
    createContent = ''
    createTags = ''
    createTemplateType = ''
    createMovieReviewData = createEmptyMovieReviewTemplateData()
    createPostVotePollData = createEmptyPostVotePollTemplateData()
    createMusicReleaseData = createEmptyMusicReleaseTemplateData()
    createError = ''
    draftError = ''
    clearLocalDraftBuffer()
    if (!draftId) {
      initialFormSnapshot = JSON.stringify(buildLocalDraftState())
      lastSavedFormSnapshot = initialFormSnapshot
      lastObservedFormSnapshot = initialFormSnapshot
    }
  }

  onMount(() => {
    const initializeForm = async () => {
      try {
        await refreshSiteUser()
        if ($siteUser) {
          await loadRubrics()
          await tick()
          initialFormSnapshot = JSON.stringify(buildLocalDraftState())
          lastSavedFormSnapshot = initialFormSnapshot
          const restored = restoreLocalDraftBuffer()
          await tick()
          lastObservedFormSnapshot = JSON.stringify(buildLocalDraftState())
          autosavePrimed = true
          if (restored && lastObservedFormSnapshot !== initialFormSnapshot) {
            queueDraftSave()
          }
        }
      } finally {
        loadingUser = false
      }
    }
    initializeForm()

    const closeOnOutsideClick = (event: MouseEvent) => {
      const target = event.target as Node | null
      if (rubricMenuOpen && rubricMenuRef && target && !rubricMenuRef.contains(target)) {
        rubricMenuOpen = false
        rubricSearchQuery = ''
      }
      if (identityMenuOpen && identityMenuRef && target && !identityMenuRef.contains(target)) {
        identityMenuOpen = false
      }
      if (templateMenuOpen && templateMenuRef && target && !templateMenuRef.contains(target)) {
        templateMenuOpen = false
      }
    }
    document.addEventListener('click', closeOnOutsideClick)
    return () => {
      document.removeEventListener('click', closeOnOutsideClick)
    }
  })

  onDestroy(() => {
    clearAutosaveTimeout()
    clearDraftSavedNotice()
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

  $: currentFormSnapshot = JSON.stringify(buildLocalDraftState())
  $: if (autosavePrimed && currentFormSnapshot !== lastObservedFormSnapshot) {
    lastObservedFormSnapshot = currentFormSnapshot
    if (currentFormSnapshot === initialFormSnapshot && !draftId) {
      lastSavedFormSnapshot = initialFormSnapshot
      clearAutosaveTimeout()
      clearLocalDraftBuffer()
      firstDraftChangeAt = null
      firstDraftAutosaveCompleted = false
      clearDraftSavedNotice()
    } else {
      if (!firstDraftChangeAt) firstDraftChangeAt = Date.now()
      if (currentFormSnapshot === initialFormSnapshot) {
        clearLocalDraftBuffer()
      } else {
        persistLocalDraftBuffer()
      }
      queueDraftSave()
    }
  }

  const createPost = async () => {
    if (!$siteUser) return
    createError = ''
    draftError = ''
    clearAutosaveTimeout()
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
      const createdPost = draftId
        ? await updateUserPost(draftId, {
            ...buildDraftPayload(),
            is_draft: false,
          })
        : await createUserPost(buildDraftPayload())
      clearLocalDraftBuffer()
      draftId = null
      resetForm()
      toast({
        content:
          'Ваш пост опубликован! Не забудьте поделиться ссылкой на него в социальных сетях',
        type: 'success',
      })
      await goto(buildBackendPostPath({ id: createdPost.id, title: createdPost.title }))
    } catch (err) {
      createError = (err as Error)?.message ?? 'Не удалось создать пост'
    } finally {
      creating = false
    }
  }

  const selectRubric = (slug: string) => {
    createRubric = slug
    rubricMenuOpen = false
    rubricSearchQuery = ''
  }

  const selectIdentity = (value: string) => {
    createAuthor = value
    identityMenuOpen = false
  }

  const selectTemplateType = (value: '' | PostTemplateType) => {
    createTemplateType = value
    templateMenuOpen = false
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
    {#if draftSavedNoticeVisible && draftId}
      <div class="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-900/20 dark:text-emerald-200">
        Материал сохранен как черновик, дальнейшее сохранение идет автоматически.
        Все черновики <a href={profileDraftsPath} class="underline decoration-emerald-500/70 underline-offset-2 hover:text-emerald-700 dark:hover:text-emerald-100">в профиле</a>.
      </div>
    {/if}
    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-6">
      <div class="flex flex-col gap-4">
        <div class="rounded-2xl bg-slate-100 px-4 py-4 dark:bg-zinc-900/80">
          <div class="flex items-start gap-3">
            <div class="h-10 w-10 shrink-0 overflow-hidden rounded-full bg-slate-200 text-sm font-semibold text-slate-600 dark:bg-zinc-800 dark:text-zinc-300">
              {#if selectedIdentity?.avatar_url}
                <img
                  src={selectedIdentity.avatar_url}
                  alt={selectedIdentity.shortLabel}
                  class="h-full w-full object-cover"
                />
              {:else}
                <div class="flex h-full w-full items-center justify-center">
                  {getAvatarFallback(selectedIdentity)}
                </div>
              {/if}
            </div>
            <div class="min-w-0 flex-1">
              <div class="relative" bind:this={identityMenuRef}>
                {#if publishIdentityOptions.length > 1}
                  <button
                    type="button"
                    class="flex max-w-full items-center gap-2 text-left text-sm font-medium leading-tight text-slate-800 dark:text-zinc-200"
                    aria-haspopup="listbox"
                    aria-expanded={identityMenuOpen}
                    on:click={() => (identityMenuOpen = !identityMenuOpen)}
                  >
                    <span class="truncate">{selectedIdentity?.shortLabel || 'Выберите автора'}</span>
                    <svg
                      class="h-5 w-5 shrink-0 text-slate-700 dark:text-zinc-300"
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
                {:else}
                  <div class="text-sm font-medium leading-tight text-slate-800 dark:text-zinc-200">
                    {selectedIdentity?.shortLabel || 'Новый пост'}
                  </div>
                {/if}

                {#if identityMenuOpen}
                  <div
                    class="absolute z-20 mt-3 w-full min-w-[18rem] max-w-xl overflow-auto rounded-2xl border border-slate-200 bg-white p-1 shadow-lg dark:border-zinc-800 dark:bg-zinc-900"
                    role="listbox"
                  >
                    {#each publishIdentityOptions as authorOption}
                      <button
                        type="button"
                        class={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left hover:bg-slate-50 dark:hover:bg-zinc-800 ${
                          createAuthor === authorOption.value ? 'bg-slate-100 dark:bg-zinc-800' : ''
                        }`}
                        on:click={() => selectIdentity(authorOption.value)}
                      >
                        <div class="h-10 w-10 shrink-0 overflow-hidden rounded-full bg-slate-200 text-sm font-semibold text-slate-600 dark:bg-zinc-700 dark:text-zinc-300">
                          {#if authorOption.avatar_url}
                            <img
                              src={authorOption.avatar_url}
                              alt={authorOption.shortLabel}
                              class="h-full w-full object-cover"
                            />
                          {:else}
                            <div class="flex h-full w-full items-center justify-center">
                              {getAvatarFallback(authorOption)}
                            </div>
                          {/if}
                        </div>
                        <div class="min-w-0 flex-1">
                          <div class="truncate text-sm font-medium text-slate-900 dark:text-zinc-100">
                            {authorOption.shortLabel}
                          </div>
                        </div>
                      </button>
                    {/each}
                  </div>
                {/if}
              </div>

              {#if rubricsLoading}
                <div class="mt-3 flex min-h-[32px] items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
                  <Spinner size="sm" />
                  Загрузка тем...
                </div>
              {:else}
                <div class="relative mt-3" bind:this={rubricMenuRef}>
                  <button
                    type="button"
                    class="flex max-w-full items-center gap-2 text-left text-sm font-medium leading-tight text-slate-800 dark:text-zinc-200"
                    aria-haspopup="listbox"
                    aria-expanded={rubricMenuOpen}
                    on:click={() => {
                      const nextState = !rubricMenuOpen
                      rubricMenuOpen = nextState
                      if (!nextState) rubricSearchQuery = ''
                    }}
                  >
                    <span class="truncate">{selectedRubric?.name || 'Без темы'}</span>
                    <svg
                      class="h-5 w-5 shrink-0 text-slate-700 dark:text-zinc-300"
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
                      class="absolute z-20 mt-3 w-full min-w-[18rem] max-w-xl overflow-auto rounded-2xl border border-slate-200 bg-white p-1 shadow-lg dark:border-zinc-800 dark:bg-zinc-900"
                      role="listbox"
                    >
                      <div class="sticky top-0 z-10 border-b border-slate-200 bg-white px-2 py-2 dark:border-zinc-800 dark:bg-zinc-900">
                        <input
                          type="text"
                          bind:value={rubricSearchQuery}
                          placeholder="Поиск рубрики"
                          class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500"
                        />
                      </div>
                      {#if filteredRubrics.length}
                        {#each filteredRubrics as rubric}
                          <button
                            type="button"
                            class={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left hover:bg-slate-50 dark:hover:bg-zinc-800 ${
                              createRubric === rubric.slug ? 'bg-slate-100 dark:bg-zinc-800' : ''
                            }`}
                            on:click={() => selectRubric(rubric.slug)}
                          >
                            <div class="h-10 w-10 shrink-0 overflow-hidden rounded-full border border-slate-200 bg-slate-100 text-sm font-semibold text-slate-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                              {#if rubric.icon_thumb_url || rubric.icon_url}
                                <img
                                  src={rubric.icon_thumb_url ?? rubric.icon_url}
                                  alt={rubric.name}
                                  class="h-full w-full object-cover"
                                />
                              {:else}
                                <div class="flex h-full w-full items-center justify-center">
                                  {rubric.name?.[0] ?? 'R'}
                                </div>
                              {/if}
                            </div>
                            <div class="min-w-0 flex-1">
                              <div class="whitespace-normal text-sm font-medium text-slate-900 dark:text-zinc-100">
                                {rubric.name}
                              </div>
                            </div>
                          </button>
                        {/each}
                      {:else}
                        <div class="px-3 py-3 text-sm text-slate-500 dark:text-zinc-400">
                          Ничего не найдено
                        </div>
                      {/if}
                    </div>
                  {/if}
                </div>

                {#if hasTemplateTypeChoice}
                  <div class="relative mt-3" bind:this={templateMenuRef}>
                    <button
                      type="button"
                      class="flex max-w-full items-center gap-2 text-left text-sm font-medium leading-tight text-slate-800 dark:text-zinc-200"
                      aria-haspopup="listbox"
                      aria-expanded={templateMenuOpen}
                      on:click={() => (templateMenuOpen = !templateMenuOpen)}
                    >
                      <span class="truncate">Тип публикации: {selectedTemplateOption.label}</span>
                      <svg
                        class="h-5 w-5 shrink-0 text-slate-700 dark:text-zinc-300"
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

                    {#if templateMenuOpen}
                      <div
                        class="absolute z-20 mt-3 w-full min-w-[18rem] max-w-xl overflow-auto rounded-2xl border border-slate-200 bg-white p-1 shadow-lg dark:border-zinc-800 dark:bg-zinc-900"
                        role="listbox"
                      >
                        {#each availableTemplateTypeOptions as templateOption}
                          <button
                            type="button"
                            class={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left hover:bg-slate-50 dark:hover:bg-zinc-800 ${
                              createTemplateType === templateOption.value
                                ? 'bg-slate-100 dark:bg-zinc-800'
                                : ''
                            }`}
                            on:click={() => selectTemplateType(templateOption.value)}
                          >
                            <div class="min-w-0 flex-1">
                              <div class="truncate text-sm font-medium text-slate-900 dark:text-zinc-100">
                                {templateOption.label}
                              </div>
                            </div>
                          </button>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {/if}
              {/if}
            </div>
          </div>
        </div>
        <TextInput label="Заголовок" bind:value={createTitle} />
        <PostTemplateFields
          bind:templateType={createTemplateType}
          bind:movieReviewData={createMovieReviewData}
          bind:postVotePollData={createPostVotePollData}
          bind:musicReleaseData={createMusicReleaseData}
          allowedTemplateTypes={selectedRubric?.allowed_template_types}
          showTypeSelector={false}
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
        {#if draftError}
          <p class="text-sm text-red-600">{draftError}</p>
        {/if}
        <div class="flex flex-wrap gap-2">
          <Button
            color="primary"
            on:click={createPost}
            loading={creating}
            disabled={creating}
          >
            Опубликовать
          </Button>
          <Button color="ghost" on:click={resetForm} disabled={creating}>
            Очистить
          </Button>
        </div>
      </div>
    </div>
  {/if}
</div>
