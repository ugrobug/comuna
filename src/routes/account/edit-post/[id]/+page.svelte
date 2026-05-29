<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import EditorAutosaveNotice from '$lib/components/editor/EditorAutosaveNotice.svelte'
  import { Button, Spinner, TextInput, toast } from 'mono-svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import { normalizeEditorJsContent } from '$lib/editorJsContent'
  import PostTemplateFields from '$lib/components/site/post-templates/PostTemplateFields.svelte'
  import { buildBackendPostPath, buildComunsUrl, type BackendComun } from '$lib/api/backend'
  import {
    fetchUserPost,
    refreshSiteUser,
    siteToken,
    siteUser,
    updateUserPost,
    type SiteUserPost,
  } from '$lib/siteAuth'
  import {
    POST_TEMPLATE_TYPE_OPTIONS,
    TWEET_TEMPLATE_MAX_LENGTH,
    buildPostTemplatePayload,
    createEmptyBugReportTemplateData,
    createEmptyMusicReleaseTemplateData,
    createEmptyMovieReviewTemplateData,
    createEmptyPostVotePollTemplateData,
    isBugReportTemplate,
    isRecognizedPostTemplateType,
    isMovieReviewTemplate,
    isMusicReleaseTemplate,
    isPostVotePollTemplate,
    isTweetTemplateType,
    normalizeAllowedPostTemplateTypeOverrides,
    normalizeAllowedPostTemplateTypes,
    normalizeBugReportTemplateData,
    normalizePostTemplateTypeOptions,
    normalizeMusicReleaseTemplateData,
    normalizeMovieReviewTemplateData,
    normalizePostVotePollTemplateData,
    normalizeTemplateEditorBlockSettings,
    resolveEnabledTemplateEditorBlockTypes,
    tweetTemplateCharacterCount,
    validateTweetTemplateContent,
    type BugReportTemplateData,
    type MusicReleaseTemplateData,
    type MovieReviewTemplateData,
    type PostTemplateType,
    type PostTemplateTypeOption,
    type PostVotePollTemplateData,
    type TemplateEditorBlockSettings,
  } from '$lib/postTemplates'
  import { deserializeEditorModel } from '$lib/util'
  import { onDestroy, onMount } from 'svelte'

  export let data: { postId: number }

  type PublishIdentityOption = {
    value: string
    label: string
    shortLabel: string
    kind: 'site'
    username?: string
    avatar_url?: string | null
  }

  const SITE_AUTHOR_CHOICE = '__site__'
  const DRAFT_NOTICE_DELAY_MS = 10_000
  const DRAFT_NOTICE_VISIBLE_MS = 5_000

  let loading = true
  let loadError = ''
  let post: SiteUserPost | null = null
  let comunsLoading = false
  let comuns: BackendComun[] = []
  let comunMenuOpen = false
  let comunSearchQuery = ''
  let comunMenuRef: HTMLDivElement | null = null
  let filteredComuns: BackendComun[] = []
  let identityMenuOpen = false
  let identityMenuRef: HTMLDivElement | null = null
  let templateMenuOpen = false
  let templateMenuRef: HTMLDivElement | null = null
  let selectedComun: BackendComun | undefined
  let publishIdentityOptions: PublishIdentityOption[] = []
  let selectedIdentity: PublishIdentityOption | undefined
  let templateEditorBlockSettings: TemplateEditorBlockSettings = {}
  let templateTypeOptions: PostTemplateTypeOption[] = POST_TEMPLATE_TYPE_OPTIONS
  let availableTemplateTypeOptions = POST_TEMPLATE_TYPE_OPTIONS
  let selectedTemplateOption = POST_TEMPLATE_TYPE_OPTIONS[0]
  let hasTemplateTypeChoice = false

  let editTitle = ''
  let editContent = ''
  let editTags = ''
  let editAuthor = ''
  let editComunSlug = ''
  let editComunCategoryId = ''
  let editTemplateType: '' | PostTemplateType = ''
  let editMovieReviewData: MovieReviewTemplateData = createEmptyMovieReviewTemplateData()
  let editPostVotePollData: PostVotePollTemplateData = createEmptyPostVotePollTemplateData()
  let editMusicReleaseData: MusicReleaseTemplateData = createEmptyMusicReleaseTemplateData()
  let editBugReportData: BugReportTemplateData = createEmptyBugReportTemplateData()
  let allowedTemplateTypes: string[] = ['basic']

  let saving = false
  let autosaving = false
  let publishing = false
  let saveError = ''
  let autosavePrimed = false
  let lastObservedEditSnapshot = ''
  let lastSavedEditSnapshot = ''
  let currentEditSnapshot = ''
  let autosaveTimeout: ReturnType<typeof setTimeout> | null = null
  let draftSavedNoticeVisible = false
  let draftSavedNoticeTimer: ReturnType<typeof setTimeout> | null = null
  let draftSavedNoticeHideTimer: ReturnType<typeof setTimeout> | null = null
  let firstDraftChangeAt: number | null = null
  let firstDraftAutosaveCompleted = false
  let tweetCharacterCountValue = 0

  $: selectedComun = comuns.find((comun) => comun.slug === editComunSlug)
  $: selectedComunCategory =
    selectedComun?.categories?.find((category) => String(category.id) === editComunCategoryId) ?? null
  $: filteredComuns = (() => {
    const query = comunSearchQuery.trim().toLowerCase()
    if (!query) return comuns
    return comuns.filter((comun) => {
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
  $: selectedIdentity = publishIdentityOptions.find((item) => item.value === editAuthor)
  $: editorEnabledTemplateBlockTypes = resolveEnabledTemplateEditorBlockTypes(
    editTemplateType,
    templateEditorBlockSettings
  )
  $: editorTemplateBlocksKey = `${editTemplateType || 'basic'}:${editorEnabledTemplateBlockTypes.join(',')}`
  $: tweetCharacterCountValue = isTweetTemplateType(editTemplateType)
    ? tweetTemplateCharacterCount(editContent)
    : 0
  $: allowedTemplateTypes = (() => {
    const values = new Set<string>(['basic'])
    for (const item of normalizeAllowedPostTemplateTypes(
      selectedComunCategory?.allowed_template_types ??
        (normalizeAllowedPostTemplateTypeOverrides(
          selectedComunCategory?.category_allowed_template_types
        ).length
          ? normalizeAllowedPostTemplateTypeOverrides(
              selectedComunCategory?.category_allowed_template_types
            )
          : selectedComun?.allowed_template_types ?? selectedComun?.allowed_post_templates)
    )) {
      values.add(item)
    }
    if (editTemplateType) values.add(editTemplateType)
    return Array.from(values)
  })()
  $: availableTemplateTypeOptions = templateTypeOptions.filter((option) =>
    option.value ? allowedTemplateTypes.includes(option.value) : allowedTemplateTypes.includes('basic')
  )
  $: hasTemplateTypeChoice = availableTemplateTypeOptions.length > 1
  $: selectedTemplateOption =
    availableTemplateTypeOptions.find((option) => option.value === editTemplateType) ??
    availableTemplateTypeOptions[0] ??
    templateTypeOptions[0] ??
    POST_TEMPLATE_TYPE_OPTIONS[0]
  $: draftSharePath =
    post?.is_draft && post?.draft_share_token
      ? `/drafts/${encodeURIComponent(post.draft_share_token)}`
      : ''
  $: draftShareUrl = draftSharePath ? `${$page.url.origin}${draftSharePath}` : ''
  $: profileDraftsPath = $siteUser?.id ? `/id${$siteUser.id}` : '/settings'

  const stripHtml = (value: string) =>
    value.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim()

  const isEditorContentEmpty = (value: string) => {
    if (!value || value.trim() === '') return true
    try {
      const data = deserializeEditorModel(value)
      return !data?.blocks || data.blocks.length === 0
    } catch {
      return stripHtml(value).length === 0
    }
  }

  const buildTags = () =>
    editTags
      .split(',')
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0)

  const buildTemplate = () =>
    buildPostTemplatePayload(
      editTemplateType,
      editMovieReviewData,
      editPostVotePollData,
      editMusicReleaseData,
      editBugReportData
    )

  const buildEditPayload = () => {
    const tags = buildTags()
    const template = buildTemplate()
    const useSiteAuthor = Boolean(post?.is_draft)
    return {
      title: editTitle,
      content: editContent.trim(),
      author_source: useSiteAuthor ? ('site' as const) : undefined,
      comun_slug: editComunSlug || undefined,
      comun_category_id: editComunCategoryId ? Number(editComunCategoryId) : null,
      tags,
      template: editTemplateType ? template : null,
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

  const getAvatarFallback = (identity: PublishIdentityOption | undefined) => {
    const source = identity?.shortLabel?.trim() || identity?.username?.trim() || 'A'
    return source.charAt(0).toUpperCase()
  }

  const scheduleDraftSavedNotice = () => {
    if (!post?.is_draft || draftSavedNoticeVisible) return
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

  const getFirstChangeAtFromUrl = () => {
    const raw = $page.url.searchParams.get('first_change_at')
    if (!raw) return null
    const parsed = Number(raw)
    if (!Number.isFinite(parsed) || parsed <= 0) return null
    return parsed
  }

  const clearFirstChangeAtFromUrl = async () => {
    if (!browser) return
    if (!$page.url.searchParams.has('first_change_at')) return
    const url = new URL($page.url)
    url.searchParams.delete('first_change_at')
    await goto(`${url.pathname}${url.search}`, {
      replaceState: true,
      noScroll: true,
      keepFocus: true,
    })
  }

  const formatSavedAt = (value?: string | null) => {
    if (!value) return ''
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ''
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  }

  const resolveAuthorValue = (currentPost: SiteUserPost) => {
    return SITE_AUTHOR_CHOICE
  }

  const fillForm = (currentPost: SiteUserPost) => {
    editTitle = currentPost.title || ''
    editContent = normalizeEditorJsContent(currentPost.content || '')
    editComunSlug =
      currentPost.comun_slug ||
      currentPost.comun?.slug ||
      ''
    editComunCategoryId = currentPost.comun_category_id ? String(currentPost.comun_category_id) : ''
    editAuthor = resolveAuthorValue(currentPost)
    editMovieReviewData = createEmptyMovieReviewTemplateData()
    editPostVotePollData = createEmptyPostVotePollTemplateData()
    editMusicReleaseData = createEmptyMusicReleaseTemplateData()
    editBugReportData = createEmptyBugReportTemplateData()
    editTemplateType = isRecognizedPostTemplateType(currentPost.template?.type)
      ? currentPost.template.type
      : ''
    if (isMovieReviewTemplate(currentPost.template)) {
      editMovieReviewData = normalizeMovieReviewTemplateData(currentPost.template.data)
    } else if (isPostVotePollTemplate(currentPost.template)) {
      editPostVotePollData = normalizePostVotePollTemplateData(currentPost.template.data)
    } else if (isMusicReleaseTemplate(currentPost.template)) {
      editMusicReleaseData = normalizeMusicReleaseTemplateData(currentPost.template.data)
    } else if (isBugReportTemplate(currentPost.template)) {
      editBugReportData = normalizeBugReportTemplateData(currentPost.template.data)
    }
    const tagNames = (currentPost.tags ?? []).map((tag) =>
      typeof tag === 'string' ? tag : tag.name
    )
    editTags = tagNames.join(', ')
    const snapshot = JSON.stringify(buildEditPayload())
    lastObservedEditSnapshot = snapshot
    lastSavedEditSnapshot = snapshot
    draftSavedNoticeVisible = false
    clearDraftSavedNoticeTimer()
    clearDraftSavedNoticeHideTimer()
    firstDraftChangeAt = null
    firstDraftAutosaveCompleted = false
    const firstChangeAtFromUrl = getFirstChangeAtFromUrl()
    if (firstChangeAtFromUrl && currentPost.is_draft) {
      firstDraftChangeAt = firstChangeAtFromUrl
      firstDraftAutosaveCompleted = true
      scheduleDraftSavedNotice()
      void clearFirstChangeAtFromUrl()
    }
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

  const loadPost = async () => {
    loading = true
    loadError = ''
    try {
      const user = await refreshSiteUser()
      if (!user) {
        await goto('/settings')
        return
      }
      await loadComuns()
      const loadedPost = await fetchUserPost(data.postId)
      post = loadedPost
      fillForm(loadedPost)
      autosavePrimed = true
    } catch (err) {
      loadError = (err as Error)?.message ?? 'Не удалось загрузить пост'
    } finally {
      loading = false
    }
  }

  const queueDraftAutosave = () => {
    if (!post?.is_draft || !autosavePrimed || autosaving || publishing) return
    clearAutosaveTimeout()
    saveError = ''
    autosaveTimeout = setTimeout(async () => {
      const postId = post?.id
      if (!postId) return
      autosaving = true
      const sentSnapshot = JSON.stringify(buildEditPayload())
      try {
        const updated = await updateUserPost(postId, {
          ...buildEditPayload(),
          is_draft: true,
        })
        post = updated
        lastSavedEditSnapshot = sentSnapshot
        lastObservedEditSnapshot = JSON.stringify(buildEditPayload())
        if (!firstDraftAutosaveCompleted) {
          firstDraftAutosaveCompleted = true
          scheduleDraftSavedNotice()
        }
      } catch (err) {
        saveError = (err as Error)?.message ?? 'Не удалось сохранить черновик'
      } finally {
        autosaving = false
        if (JSON.stringify(buildEditPayload()) !== lastSavedEditSnapshot) {
          queueDraftAutosave()
        }
      }
    }, 900)
  }

  const flushDraftAutosave = async (options?: { keepalive?: boolean }) => {
    const postId = post?.id
    if (!post?.is_draft || !postId || !autosavePrimed || publishing) return
    const targetSnapshot = JSON.stringify(buildEditPayload())
    if (targetSnapshot === lastSavedEditSnapshot) return
    clearAutosaveTimeout()

    try {
      const updated = await updateUserPost(postId, {
        ...buildEditPayload(),
        is_draft: true,
      }, options)
      post = updated
      lastSavedEditSnapshot = targetSnapshot
      lastObservedEditSnapshot = targetSnapshot
      saveError = ''
      if (!firstDraftAutosaveCompleted) {
        firstDraftAutosaveCompleted = true
        scheduleDraftSavedNotice()
      }
    } catch (err) {
      saveError = (err as Error)?.message ?? 'Не удалось сохранить черновик'
    }
  }

  const validateForPublish = () => {
    if (!editTitle.trim()) {
      saveError = 'Укажите заголовок поста'
      return false
    }
    const trimmedContent = editContent.trim()
    if (!trimmedContent || isEditorContentEmpty(trimmedContent)) {
      saveError = 'Текст поста не может быть пустым'
      return false
    }
    if (!editComunSlug) {
      saveError = 'Выберите сообщество'
      return false
    }
    if (isTweetTemplateType(editTemplateType)) {
      const tweetValidationError = validateTweetTemplateContent(editContent)
      if (tweetValidationError) {
        saveError = tweetValidationError
        return false
      }
    }
    return true
  }

  const savePublishedEdit = async () => {
    if (!post) return
    saving = true
    saveError = ''
    clearAutosaveTimeout()
    try {
      if (!validateForPublish()) {
        saving = false
        return
      }
      const updated = await updateUserPost(post.id, buildEditPayload())
      post = updated
      fillForm(updated)
      toast({ content: 'Пост обновлён', type: 'success' })
    } catch (err) {
      saveError = (err as Error)?.message ?? 'Не удалось сохранить изменения'
    } finally {
      saving = false
    }
  }

  const publishDraft = async () => {
    if (!post || saving) return
    publishing = true
    saveError = ''
    clearAutosaveTimeout()
    try {
      if (!validateForPublish()) {
        publishing = false
        return
      }
      const updated = await updateUserPost(post.id, {
        ...buildEditPayload(),
        is_draft: false,
      })
      toast({ content: 'Черновик опубликован', type: 'success' })
      await goto(buildBackendPostPath({ id: updated.id, title: updated.title }))
    } catch (err) {
      saveError = (err as Error)?.message ?? 'Не удалось опубликовать черновик'
    } finally {
      publishing = false
    }
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
    await flushDraftAutosave()
    if (!post?.id) return
    await goto(`/account/edit-post/${post.id}/preview`)
  }

  const selectComun = (slug: string) => {
    editComunSlug = slug
    editComunCategoryId = ''
    comunMenuOpen = false
    comunSearchQuery = ''
  }

  const selectIdentity = (value: string) => {
    editAuthor = value
    identityMenuOpen = false
  }

  const selectTemplateType = (value: '' | PostTemplateType) => {
    editTemplateType = value
    templateMenuOpen = false
  }

  onMount(() => {
    loadPost()

    const flushOnPageHide = () => {
      void flushDraftAutosave({ keepalive: true })
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        void flushDraftAutosave({ keepalive: true })
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
    clearDraftSavedNoticeTimer()
    clearDraftSavedNoticeHideTimer()
  })

  $: if (
    editComunSlug &&
    editComunCategoryId &&
    !selectedComun?.categories?.some((category) => String(category.id) === editComunCategoryId)
  ) {
    editComunCategoryId = ''
  }

  $: currentEditSnapshot = JSON.stringify(buildEditPayload())
  $: if (autosavePrimed && post?.is_draft && currentEditSnapshot !== lastObservedEditSnapshot) {
    if (!firstDraftChangeAt) firstDraftChangeAt = Date.now()
    lastObservedEditSnapshot = currentEditSnapshot
    queueDraftAutosave()
  }
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">
      {#if post?.is_draft}Черновик{:else}Редактирование поста{/if}
    </h1>
  </Header>

  {#if loading}
    <div class="flex items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
      <Spinner size="sm" />
      Загрузка...
    </div>
  {:else if loadError}
    <p class="text-sm text-red-600">{loadError}</p>
  {:else if post}
    <EditorAutosaveNotice visible={draftSavedNoticeVisible && post.is_draft} href={profileDraftsPath} />
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
                    {selectedIdentity?.shortLabel || 'Редактирование'}
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
                          editAuthor === authorOption.value ? 'bg-slate-100 dark:bg-zinc-800' : ''
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
                    <span class="truncate">{selectedComun?.name || 'Выберите сообщество'}</span>
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
                        {#each filteredComuns as comun}
                          <button
                            type="button"
                            class={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left hover:bg-slate-50 dark:hover:bg-zinc-800 ${
                              editComunSlug === comun.slug ? 'bg-slate-100 dark:bg-zinc-800' : ''
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
                      {:else}
                        <div class="px-3 py-3 text-sm text-slate-500 dark:text-zinc-400">
                          Ничего не найдено
                        </div>
                      {/if}
                    </div>
                  {/if}
                </div>

                {#if selectedComun?.categories?.length}
                  <div class="mt-3">
                    <label
                      for="edit-post-comun-category"
                      class="mb-1 block text-xs font-medium uppercase tracking-[0.1em] text-slate-500 dark:text-zinc-500"
                    >
                      Раздел сообщества
                    </label>
                    <select
                      id="edit-post-comun-category"
                      bind:value={editComunCategoryId}
                      class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500"
                    >
                      <option value="">Без раздела</option>
                      {#each selectedComun.categories as category}
                        <option value={String(category.id)}>{category.name}</option>
                      {/each}
                    </select>
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
                              editTemplateType === templateOption.value ? 'bg-slate-100 dark:bg-zinc-800' : ''
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

        <TextInput label="Заголовок" bind:value={editTitle} />
        <PostTemplateFields
          bind:templateType={editTemplateType}
          bind:movieReviewData={editMovieReviewData}
          bind:postVotePollData={editPostVotePollData}
          bind:musicReleaseData={editMusicReleaseData}
          bind:bugReportData={editBugReportData}
          {allowedTemplateTypes}
          {templateTypeOptions}
          showTypeSelector={false}
        />

        <div class="flex flex-col gap-2">
          {#key `edit-editor-template-${editorTemplateBlocksKey}`}
            <EditorJS
              bind:value={editContent}
              placeholder="Текст поста"
              postTemplateType={editTemplateType}
              enabledTemplateEditorBlockTypes={editorEnabledTemplateBlockTypes}
              glossaryTerms={
                selectedComun?.glossary_enabled ? selectedComun?.glossary_terms ?? [] : []
              }
              enableAutosave={false}
              postId={post.id}
              showPostSettings={false}
            />
          {/key}
          {#if isTweetTemplateType(editTemplateType)}
            <div class={`rounded-xl border px-3 py-2 text-sm ${
              tweetCharacterCountValue > TWEET_TEMPLATE_MAX_LENGTH
                ? 'border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/20 dark:text-rose-300'
                : 'border-slate-200 bg-slate-50 text-slate-600 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-300'
            }`}>
              <div class="flex flex-wrap items-center justify-between gap-2">
                <span>Текст твита: {tweetCharacterCountValue} / {TWEET_TEMPLATE_MAX_LENGTH}</span>
                <span>Разрешен один медиаблок с изображениями</span>
              </div>
            </div>
          {/if}
        </div>

        <TextInput label="Теги (через запятую)" bind:value={editTags} />

        {#if saveError}
          <p class="text-sm text-red-600">{saveError}</p>
        {/if}

        <div class="flex flex-wrap gap-2">
          {#if post.is_draft}
            <Button
              color="primary"
              on:click={publishDraft}
              loading={publishing}
              disabled={publishing}
            >
              Опубликовать
            </Button>
            <Button color="ghost" on:click={copyDraftShareLink} disabled={!draftShareUrl || publishing}>
              Поделиться
            </Button>
            {#if draftSharePath}
              <Button color="ghost" on:click={openDraftPreview} disabled={publishing}>
                Предпросмотр
              </Button>
            {/if}
          {:else}
            <Button color="primary" on:click={savePublishedEdit} loading={saving} disabled={saving}>
              Сохранить
            </Button>
            <Button
              color="ghost"
              href={buildBackendPostPath({ id: post.id, title: post.title })}
              target="_blank"
              rel="noreferrer"
              disabled={saving}
            >
              Открыть пост
            </Button>
            <Button color="ghost" href="/settings" disabled={saving || publishing}>
              Назад к настройкам
            </Button>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>
