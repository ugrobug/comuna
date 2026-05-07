<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import EditorAutosaveNotice from '$lib/components/editor/EditorAutosaveNotice.svelte'
  import { Button, Spinner, TextInput, toast } from 'mono-svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import { onDestroy, onMount, tick } from 'svelte'
  import { deserializeEditorModel, postPayloadContainsExternalLinks } from '$lib/util'
  import {
    createUserPost,
    createComunPost,
    fetchUserPost,
    refreshSiteUser,
    siteToken,
    siteUser,
    updateUserPost,
  } from '$lib/siteAuth'
  import {
    buildComunsUrl,
    type BackendComun,
  } from '$lib/api/backend'
  import PostTemplateFields from '$lib/components/site/post-templates/PostTemplateFields.svelte'
  import {
    POST_TEMPLATE_TYPE_OPTIONS,
    buildPostTemplatePayload,
    createEmptyMusicReleaseTemplateData,
    createEmptyMovieReviewTemplateData,
    createEmptyPostVotePollTemplateData,
    normalizeAllowedPostTemplateTypeOverrides,
    normalizeAllowedPostTemplateTypes,
    normalizePostTemplateTypeOptions,
    normalizeTemplateEditorBlockSettings,
    resolveEnabledTemplateEditorBlockTypes,
    type MusicReleaseTemplateData,
    type MovieReviewTemplateData,
    type PostVotePollTemplateData,
    type PostTemplateType,
    type PostTemplateTypeOption,
    type TemplateEditorBlockSettings,
  } from '$lib/postTemplates'

  let loadingUser = true
  let createTitle = ''
  let createContent = ''
  let createTags = ''
  let createAuthor = ''
  let createComunSlug = ''
  let createComunCategoryId = ''
  let creating = false
  let createError = ''
  let draftError = ''
  let draftCreating = false
  let draftId: number | null = null
  let draftShareToken = ''
  let comunsLoading = false
  let autosavePrimed = false
  let initialFormSnapshot = ''
  let lastSavedFormSnapshot = ''
  let lastObservedFormSnapshot = ''
  let currentFormSnapshot = ''
  let autosaveTimeout: ReturnType<typeof setTimeout> | null = null
  let comunMenuOpen = false
  let comunSearchQuery = ''
  let comunMenuRef: HTMLDivElement | null = null
  let filteredComuns: BackendComun[] = []
  let identityMenuOpen = false
  let identityMenuRef: HTMLDivElement | null = null
  let templateMenuOpen = false
  let templateMenuRef: HTMLDivElement | null = null
  let hasTemplateTypeChoice = false
  let allowedTemplateTypeSet = new Set<string>()
  let templateTypeOptions: PostTemplateTypeOption[] = POST_TEMPLATE_TYPE_OPTIONS
  let availableTemplateTypeOptions = POST_TEMPLATE_TYPE_OPTIONS
  let selectedTemplateOption = POST_TEMPLATE_TYPE_OPTIONS[0]
  let publishIdentityOptions: PublishIdentityOption[] = []
  let selectedIdentity: PublishIdentityOption | undefined
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
  let comuns: BackendComun[] = []

  const DRAFT_NOTICE_DELAY_MS = 10_000
  const DRAFT_NOTICE_VISIBLE_MS = 5_000
  $: requestedComunSlug = String($page.url.searchParams.get('comun') || '').trim()
  $: requestedNewPost = $page.url.searchParams.get('new') === '1'

  type PublishIdentityOption = {
    value: string
    label: string
    shortLabel: string
    kind: 'site'
    username?: string
    avatar_url?: string | null
  }

  $: availableComuns = comuns.filter((comun) => Boolean(comun.can_post))
  $: selectedComun = availableComuns.find((comun) => comun.slug === createComunSlug)
  $: selectedComunCategories = selectedComun?.categories ?? []
  $: selectedTargetLabel = selectedComun?.name || 'Выберите сообщество'
  $: selectedComunCategory =
    selectedComunCategories.find((category) => String(category.id) === createComunCategoryId) ?? null
  $: selectedCategoryOnlyModeratorsCanPost = Boolean(
    selectedComunCategory?.only_moderators_can_post
  )
  $: selectedCategoryRestrictedForCurrentUser = Boolean(
    selectedCategoryOnlyModeratorsCanPost && !selectedComun?.can_moderate
  )
  $: selectedAllowedTemplateTypes = normalizeAllowedPostTemplateTypes(
    selectedComunCategory?.allowed_template_types ??
      (normalizeAllowedPostTemplateTypeOverrides(
        selectedComunCategory?.category_allowed_template_types
      ).length
        ? normalizeAllowedPostTemplateTypeOverrides(
            selectedComunCategory?.category_allowed_template_types
          )
        : selectedComun?.allowed_template_types ?? selectedComun?.allowed_post_templates)
  )
  $: filteredComuns = (() => {
    const query = comunSearchQuery.trim().toLowerCase()
    if (!query) return availableComuns
    return availableComuns.filter((comun) => {
      const name = (comun.name || '').toLowerCase()
      const slug = (comun.slug || '').toLowerCase()
      const description = (comun.product_description || '').toLowerCase()
      return name.includes(query) || slug.includes(query) || description.includes(query)
    })
  })()
  $: publishIdentityOptions = (() => {
    if (!$siteUser) return [] as PublishIdentityOption[]
    const siteLabelBase = ($siteUser.display_name || '').trim() || `@${$siteUser.username}`
    return [
      {
        value: SITE_AUTHOR_CHOICE,
        label: siteLabelBase,
        shortLabel: siteLabelBase,
        kind: 'site',
        username: $siteUser.username,
        avatar_url: $siteUser.avatar_url ?? null,
      },
    ]
  })()
  $: selectedIdentity = publishIdentityOptions.find((item) => item.value === createAuthor)
  $: allowedTemplateTypeSet = new Set(selectedAllowedTemplateTypes)
  $: availableTemplateTypeOptions = templateTypeOptions.filter((option) =>
    option.value ? allowedTemplateTypeSet.has(option.value) : allowedTemplateTypeSet.has('basic')
  )
  $: hasTemplateTypeChoice = availableTemplateTypeOptions.length > 1
  $: selectedTemplateOption =
    availableTemplateTypeOptions.find((option) => option.value === createTemplateType) ??
    availableTemplateTypeOptions[0] ??
    templateTypeOptions[0] ??
    POST_TEMPLATE_TYPE_OPTIONS[0]
  $: profileDraftsPath = $siteUser?.id ? `/id${$siteUser.id}` : '/settings'
  $: draftSharePath = draftShareToken ? `/drafts/${encodeURIComponent(draftShareToken)}` : ''
  $: draftShareUrl = draftSharePath && browser ? `${window.location.origin}${draftSharePath}` : ''
  $: draftPreviewPath = draftId ? `/account/edit-post/${draftId}/preview` : ''
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
      author_source: 'site' as const,
      comun_slug: createComunSlug || undefined,
      comun_category_id: createComunCategoryId ? Number(createComunCategoryId) : null,
      tags: tags.length ? tags : undefined,
      template: template ?? undefined,
    }
  }

  const buildLocalDraftState = () => ({
    title: createTitle,
    content: createContent,
    tags: createTags,
    author: createAuthor,
    comunSlug: createComunSlug,
    comunCategoryId: createComunCategoryId,
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
      const nextComunSlug = String(parsed?.comunSlug || '')
      const nextComunCategoryId = String(parsed?.comunCategoryId || '')
      const nextTemplateType = String(parsed?.templateType || '') as '' | PostTemplateType
      const nextDraftId = Number(parsed?.draft_id ?? 0)
      const nextFirstChangeAt = Number(parsed?.first_change_at ?? 0)
      const authorExists =
        !nextAuthor || publishIdentityOptions.some((item) => item.value === nextAuthor)
      const comunExists = !nextComunSlug || availableComuns.some((item) => item.slug === nextComunSlug)
      createTitle = String(parsed?.title || '')
      createContent = String(parsed?.content || '')
      createTags = String(parsed?.tags || '')
      createAuthor = authorExists ? nextAuthor : createAuthor
      createComunSlug = comunExists ? nextComunSlug : ''
      createComunCategoryId = comunExists ? nextComunCategoryId : ''
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

  const isMissingDraftError = (error: unknown) => {
    const message = ((error as Error)?.message || '').toLowerCase()
    return (
      message.includes('post not found') ||
      message.includes('draft not found') ||
      message.includes('черновик не найден') ||
      message.includes('пост не найден')
    )
  }

  const saveDraftRecord = async (options?: { keepalive?: boolean }) => {
    if (!draftId) {
      return await createUserPost({
        ...buildDraftPayload(),
        is_draft: true,
      }, options)
    }

    try {
      return await updateUserPost(draftId, {
        ...buildDraftPayload(),
        is_draft: true,
      }, options)
    } catch (error) {
      if (!isMissingDraftError(error)) throw error
      draftId = null
      draftShareToken = ''
      persistLocalDraftBuffer()
      return await createUserPost({
        ...buildDraftPayload(),
        is_draft: true,
      }, options)
    }
  }

  const validateRestoredDraftId = async () => {
    if (!draftId) return
    try {
      const restoredDraft = await fetchUserPost(draftId)
      draftShareToken = restoredDraft.draft_share_token ?? ''
    } catch (error) {
      if (!isMissingDraftError(error)) return
      draftId = null
      draftShareToken = ''
      firstDraftAutosaveCompleted = false
      persistLocalDraftBuffer()
    }
  }

  const flushDraftSave = async (options?: { keepalive?: boolean; allowWhileCreating?: boolean }) => {
    if (!autosavePrimed || !$siteUser || creating) return
    const targetSnapshot = JSON.stringify(buildLocalDraftState())
    if (targetSnapshot === lastSavedFormSnapshot) return
    if (draftCreating && !draftId && !options?.allowWhileCreating) return

    clearAutosaveTimeout()

    try {
      const previousDraftId = draftId
      const draft = await saveDraftRecord(options)
      const isFirstSave = !previousDraftId || previousDraftId !== draft.id
      draftId = draft.id
      draftShareToken = draft.draft_share_token ?? ''
      draftError = ''
      lastSavedFormSnapshot = targetSnapshot
      persistLocalDraftBuffer()
      if (isFirstSave || !firstDraftAutosaveCompleted) {
        firstDraftAutosaveCompleted = true
        scheduleDraftSavedNotice()
      }
    } catch (error) {
      draftError = (error as Error)?.message ?? 'Не удалось сохранить черновик'
    }
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

  const loadComuns = async () => {
    if (comunsLoading) return
    comunsLoading = true
    const headers: Record<string, string> = {}
    if ($siteToken) {
      headers.Authorization = `Bearer ${$siteToken}`
    }
    try {
      const response = await fetch(buildComunsUrl(), {
        headers,
        cache: 'no-store',
      })
      const data = await response.json().catch(() => ({}))
      comuns = Array.isArray(data?.comuns)
        ? data.comuns.map((comun: BackendComun) => ({
            ...comun,
            allowed_template_types: normalizeAllowedPostTemplateTypes(
              comun?.allowed_template_types ?? comun?.allowed_post_templates
            ),
          }))
        : []
      templateEditorBlockSettings = normalizeTemplateEditorBlockSettings(
        data?.template_editor_blocks_by_template
      )
      templateTypeOptions = normalizePostTemplateTypeOptions(
        data?.template_type_options ?? data?.template_types
      )
    } catch {
      comuns = []
    } finally {
      comunsLoading = false
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
      try {
        await flushDraftSave({ allowWhileCreating: true })
      } catch (error) {
        draftError = (error as Error)?.message ?? 'Не удалось сохранить черновик'
      } finally {
        draftCreating = false
        if (currentFormSnapshot !== lastSavedFormSnapshot) {
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
    draftShareToken = ''
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
          await loadComuns()
          await tick()
          initialFormSnapshot = JSON.stringify(buildLocalDraftState())
          lastSavedFormSnapshot = initialFormSnapshot
          if (requestedNewPost) {
            clearLocalDraftBuffer()
          }
          const restored = requestedNewPost ? false : restoreLocalDraftBuffer()
          if (requestedComunSlug) {
            const requestedComun = comuns.find(
              (comun) => comun.slug === requestedComunSlug && Boolean(comun.can_post)
            )
            if (requestedComun) {
              createComunSlug = requestedComun.slug
              createComunCategoryId = ''
            }
          }
          if (restored) {
            await validateRestoredDraftId()
          }
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

    const flushOnPageHide = () => {
      void flushDraftSave({ keepalive: true })
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        void flushDraftSave({ keepalive: true })
      }
    }

    const closeOnOutsideClick = (event: MouseEvent) => {
      const target = event.target as Node | null
      if (comunMenuOpen && comunMenuRef && target && !comunMenuRef.contains(target)) {
        comunMenuOpen = false
        comunSearchQuery = ''
      }
      if (identityMenuOpen && identityMenuRef && target && !identityMenuRef.contains(target)) {
        identityMenuOpen = false
      }
      if (templateMenuOpen && templateMenuRef && target && !templateMenuRef.contains(target)) {
        templateMenuOpen = false
      }
    }
    document.addEventListener('click', closeOnOutsideClick)
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('pagehide', flushOnPageHide)
    return () => {
      document.removeEventListener('click', closeOnOutsideClick)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('pagehide', flushOnPageHide)
    }
  })

  onDestroy(() => {
    clearAutosaveTimeout()
    clearDraftSavedNotice()
  })

  $: if ($siteUser && !createAuthor) {
    createAuthor = SITE_AUTHOR_CHOICE
  }
  $: if (
    createComunSlug &&
    createComunCategoryId &&
    !selectedComunCategories.some((category) => String(category.id) === createComunCategoryId)
  ) {
    createComunCategoryId = ''
  }
  $: if (createTemplateType && !selectedAllowedTemplateTypes.includes(createTemplateType)) {
    createTemplateType = availableTemplateTypeOptions[0]?.value ?? ''
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
    if (!createComunSlug) {
      createError = 'Выберите сообщество для публикации.'
      return
    }
    if (selectedCategoryRestrictedForCurrentUser) {
      createError = `Публикация в категории "${selectedComunCategory?.name ?? ''}" доступна только создателю и модераторам.`
      return
    }
    const template = buildTemplate()
    if (
      selectedComun?.forbid_external_links &&
      postPayloadContainsExternalLinks({
        title: createTitle.trim(),
        content: createContent.trim(),
        template,
      })
    ) {
      createError =
        'В этом сообществе запрещены внешние ссылки. Удалите ссылки из текста и шаблона публикации.'
      return
    }
    creating = true
    try {
      await createComunPost(createComunSlug, {
        title: createTitle.trim(),
        content: createContent.trim(),
        author_source: 'site' as const,
        comun_category_id: createComunCategoryId ? Number(createComunCategoryId) : null,
        template: template ?? undefined,
      })
      clearLocalDraftBuffer()
      draftId = null
      draftShareToken = ''
      resetForm()
      toast({
        content:
          'Ваш пост опубликован! Не забудьте поделиться ссылкой на него в социальных сетях',
        type: 'success',
      })
      await goto(`/comuns/${encodeURIComponent(createComunSlug)}`)
    } catch (err) {
      createError = (err as Error)?.message ?? 'Не удалось создать пост'
    } finally {
      creating = false
    }
  }

  const selectComun = (slug: string) => {
    createComunSlug = slug
    createComunCategoryId = ''
    comunMenuOpen = false
    comunSearchQuery = ''
  }

  const selectIdentity = (value: string) => {
    createAuthor = value
    identityMenuOpen = false
  }

  const selectTemplateType = (value: '' | PostTemplateType) => {
    createTemplateType = value
    templateMenuOpen = false
  }

  const copyDraftShareLink = async () => {
    if (!draftShareUrl) return
    try {
      await navigator.clipboard.writeText(draftShareUrl)
      toast({ content: 'Ссылка на черновик скопирована', type: 'success' })
    } catch {
      toast({ content: 'Не удалось скопировать ссылку', type: 'error' })
    }
  }

  const openDraftPreview = async () => {
    await flushDraftSave()
    if (!draftPreviewPath) return
    await goto(draftPreviewPath)
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
    <EditorAutosaveNotice visible={draftSavedNoticeVisible && !!draftId} href={profileDraftsPath} />
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

              {#if comunsLoading}
                <div class="mt-3 flex min-h-[32px] items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
                  <Spinner size="sm" />
                  Загрузка сообществ...
                </div>
              {:else}
                <div class="relative mt-3" bind:this={comunMenuRef}>
                  <button
                    type="button"
                    class="flex max-w-full items-center gap-2 text-left text-sm font-medium leading-tight text-slate-800 dark:text-zinc-200"
                    aria-haspopup="listbox"
                    aria-expanded={comunMenuOpen}
                    on:click={() => {
                      const nextState = !comunMenuOpen
                      comunMenuOpen = nextState
                      if (!nextState) comunSearchQuery = ''
                    }}
                  >
                    <span class="truncate">{selectedTargetLabel}</span>
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

                  {#if comunMenuOpen}
                    <div
                      class="absolute z-20 mt-3 w-full min-w-[18rem] max-w-xl overflow-auto rounded-2xl border border-slate-200 bg-white p-1 shadow-lg dark:border-zinc-800 dark:bg-zinc-900"
                      role="listbox"
                    >
                      <div class="sticky top-0 z-10 border-b border-slate-200 bg-white px-2 py-2 dark:border-zinc-800 dark:bg-zinc-900">
                        <input
                          type="text"
                          bind:value={comunSearchQuery}
                          placeholder="Поиск сообщества"
                          class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500"
                        />
                      </div>
                      {#if filteredComuns.length}
                        <div class="px-3 pb-1 pt-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-zinc-500">
                          Сообщества
                        </div>
                        {#each filteredComuns as comun}
                          <button
                            type="button"
                            class={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left hover:bg-slate-50 dark:hover:bg-zinc-800 ${
                              createComunSlug === comun.slug ? 'bg-slate-100 dark:bg-zinc-800' : ''
                            }`}
                            on:click={() => selectComun(comun.slug)}
                          >
                            <div class="h-10 w-10 shrink-0 overflow-hidden rounded-full border border-slate-200 bg-slate-100 text-sm font-semibold text-slate-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                              {#if comun.logo_url}
                                <img
                                  src={comun.logo_url}
                                  alt={comun.name}
                                  class="h-full w-full object-cover"
                                />
                              {:else}
                                <div class="flex h-full w-full items-center justify-center">
                                  {comun.name?.[0] ?? 'C'}
                                </div>
                              {/if}
                            </div>
                            <div class="min-w-0 flex-1">
                              <div class="whitespace-normal text-sm font-medium text-slate-900 dark:text-zinc-100">
                                {comun.name}
                              </div>
                              {#if comun.product_description}
                                <div class="mt-1 line-clamp-2 text-xs text-slate-500 dark:text-zinc-400">
                                  {comun.product_description}
                                </div>
                              {/if}
                            </div>
                          </button>
                        {/each}
                      {/if}
                      {#if !filteredComuns.length}
                        <div class="px-3 py-3 text-sm text-slate-500 dark:text-zinc-400">
                          Ничего не найдено
                        </div>
                      {/if}
                    </div>
                  {/if}
                </div>

                {#if selectedComun && selectedComunCategories.length}
                  <div class="mt-3">
                    <label
                      for="new-post-comun-category"
                      class="mb-1 block text-xs font-medium uppercase tracking-[0.1em] text-slate-500 dark:text-zinc-500"
                    >
                      Раздел комуны
                    </label>
                    <select
                      id="new-post-comun-category"
                      bind:value={createComunCategoryId}
                      class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500"
                    >
                      <option value="">Без раздела</option>
                      {#each selectedComunCategories as category}
                        <option value={String(category.id)}>{category.name}</option>
                      {/each}
                    </select>
                  </div>
                {/if}

                {#if selectedCategoryRestrictedForCurrentUser}
                  <div class="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-3 text-sm text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200">
                    В категории "{selectedComunCategory?.name}" писать могут только администраторы и модераторы сообщества.
                  </div>
                {/if}

                {#if selectedComun?.rules_text}
                  <div class="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm dark:border-zinc-800 dark:bg-zinc-900/80">
                    <div class="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-zinc-500">
                      Правила сообщества
                    </div>
                    <div class="mt-2 whitespace-pre-line leading-relaxed text-slate-700 dark:text-zinc-300">
                      {selectedComun.rules_text}
                    </div>
                  </div>
                {/if}

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
                              <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">
                                {templateOption.label}
                              </div>
                              {#if templateOption.description}
                                <div class="mt-1 text-xs leading-snug text-slate-500 dark:text-zinc-400">
                                  {templateOption.description}
                                </div>
                              {/if}
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
          allowedTemplateTypes={selectedAllowedTemplateTypes}
          {templateTypeOptions}
          showTypeSelector={false}
        />
        {#key `editor-template-${editorTemplateBlocksKey}`}
          <EditorJS
            bind:value={createContent}
            placeholder="Текст поста"
            postTemplateType={createTemplateType}
            enabledTemplateEditorBlockTypes={editorEnabledTemplateBlockTypes}
            glossaryTerms={
              selectedComun?.glossary_enabled ? selectedComun?.glossary_terms ?? [] : []
            }
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
          {#if draftId}
            <Button color="ghost" on:click={copyDraftShareLink} disabled={!draftShareUrl || creating}>
              Поделиться
            </Button>
            <Button color="ghost" on:click={openDraftPreview} disabled={creating}>
              Предпросмотр
            </Button>
          {/if}
          <Button color="ghost" on:click={resetForm} disabled={creating}>
            Очистить
          </Button>
        </div>
      </div>
    </div>
  {/if}
</div>
