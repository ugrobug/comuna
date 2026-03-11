<script lang="ts">
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Spinner, TextInput, toast } from 'mono-svelte'
  import TipTapEditor from '$lib/components/editor/TipTapEditor.svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import PostTemplateFields from '$lib/components/site/post-templates/PostTemplateFields.svelte'
  import { buildBackendPostPath, buildRubricsUrl } from '$lib/api/backend'
  import {
    fetchUserPost,
    refreshSiteUser,
    siteToken,
    siteUser,
    updateUserPost,
    type SiteUserPost,
  } from '$lib/siteAuth'
  import {
    buildPostTemplatePayload,
    createEmptyMusicReleaseTemplateData,
    createEmptyMovieReviewTemplateData,
    createEmptyPostVotePollTemplateData,
    isMovieReviewTemplate,
    isMusicReleaseTemplate,
    isPostVotePollTemplate,
    normalizeAllowedPostTemplateTypes,
    normalizeMusicReleaseTemplateData,
    normalizeMovieReviewTemplateData,
    normalizePostVotePollTemplateData,
    normalizeTemplateEditorBlockSettings,
    resolveEnabledTemplateEditorBlockTypes,
    type MusicReleaseTemplateData,
    type MovieReviewTemplateData,
    type PostTemplateType,
    type PostVotePollTemplateData,
    type TemplateEditorBlockSettings,
  } from '$lib/postTemplates'
  import { deserializeEditorModel } from '$lib/util'
  import { onDestroy, onMount } from 'svelte'

  export let data: { postId: number }

  type RubricOption = {
    name: string
    slug: string
    icon_url?: string | null
    icon_thumb_url?: string | null
    allowed_template_types?: string[]
  }

  type PublishIdentityOption = {
    value: string
    label: string
    kind: 'site' | 'channel'
    username?: string
    rubric_slug?: string | null
  }

  const SITE_AUTHOR_CHOICE = '__site__'
  const DRAFT_NOTICE_DELAY_MS = 10_000

  let loading = true
  let loadError = ''
  let post: SiteUserPost | null = null
  let rubricsLoading = false
  let rubrics: RubricOption[] = []
  let rubricMenuOpen = false
  let rubricMenuRef: HTMLDivElement | null = null
  let selectedRubric: RubricOption | undefined
  let publishIdentityOptions: PublishIdentityOption[] = []
  let selectedIdentity: PublishIdentityOption | undefined
  let selectedChannelIdentity: PublishIdentityOption | undefined
  let templateEditorBlockSettings: TemplateEditorBlockSettings = {}

  let editTitle = ''
  let editContent = ''
  let editTags = ''
  let editAuthor = ''
  let editRubric = ''
  let isJsonContent = true
  let editTemplateType: '' | PostTemplateType = ''
  let editMovieReviewData: MovieReviewTemplateData = createEmptyMovieReviewTemplateData()
  let editPostVotePollData: PostVotePollTemplateData = createEmptyPostVotePollTemplateData()
  let editMusicReleaseData: MusicReleaseTemplateData = createEmptyMusicReleaseTemplateData()
  let allowedTemplateTypes: string[] = ['basic']

  let saving = false
  let autosaving = false
  let publishing = false
  let saveError = ''
  let autosavePrimed = false
  let lastObservedEditSnapshot = ''
  let autosaveTimeout: ReturnType<typeof setTimeout> | null = null
  let draftSavedNoticeVisible = false
  let draftSavedNoticeTimer: ReturnType<typeof setTimeout> | null = null
  let firstDraftChangeAt: number | null = null
  let firstDraftAutosaveCompleted = false

  $: selectedRubric = rubrics.find((rubric) => rubric.slug === editRubric)
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
  $: selectedIdentity = publishIdentityOptions.find((item) => item.value === editAuthor)
  $: selectedChannelIdentity = selectedIdentity?.kind === 'channel' ? selectedIdentity : undefined
  $: editorEnabledTemplateBlockTypes = resolveEnabledTemplateEditorBlockTypes(
    editTemplateType,
    templateEditorBlockSettings
  )
  $: editorTemplateBlocksKey = `${editTemplateType || 'basic'}:${editorEnabledTemplateBlockTypes.join(',')}`
  $: allowedTemplateTypes = (() => {
    const values = new Set<string>(['basic'])
    for (const item of normalizeAllowedPostTemplateTypes(selectedRubric?.allowed_template_types)) {
      values.add(item)
    }
    if (editTemplateType) values.add(editTemplateType)
    return Array.from(values)
  })()
  $: draftSharePath =
    post?.is_draft && post?.draft_share_token
      ? `/drafts/${encodeURIComponent(post.draft_share_token)}`
      : ''
  $: draftShareUrl = draftSharePath ? `${$page.url.origin}${draftSharePath}` : ''
  $: profileDraftsPath = $siteUser?.id ? `/id${$siteUser.id}` : '/settings'

  const detectContentType = (content: string): boolean => {
    if (!content || content.trim() === '') {
      return true
    }
    if (content.trim().startsWith('<') && content.trim().endsWith('>')) {
      return false
    }
    try {
      const parsed = JSON.parse(content)
      return parsed && typeof parsed === 'object' && 'blocks' in parsed
    } catch {
      try {
        const isBase64 = /^[A-Za-z0-9+/]*={0,2}$/.test(content)
        if (!isBase64) {
          return false
        }
        const decoded = deserializeEditorModel(content)
        return decoded && typeof decoded === 'object' && 'blocks' in decoded
      } catch {
        return false
      }
    }
  }

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
      editMusicReleaseData
    )

  const buildEditPayload = () => {
    const tags = buildTags()
    const template = buildTemplate()
    return {
      title: editTitle,
      content: editContent.trim(),
      author_source: editAuthor === SITE_AUTHOR_CHOICE ? ('site' as const) : undefined,
      author_username:
        editAuthor && editAuthor !== SITE_AUTHOR_CHOICE
          ? editAuthor.replace(/^channel:/, '')
          : undefined,
      rubric_slug: editRubric || undefined,
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

  const scheduleDraftSavedNotice = () => {
    if (!post?.is_draft || draftSavedNoticeVisible) return
    clearDraftSavedNoticeTimer()
    const elapsed = Date.now() - (firstDraftChangeAt ?? Date.now())
    const delay = Math.max(0, DRAFT_NOTICE_DELAY_MS - elapsed)
    draftSavedNoticeTimer = setTimeout(() => {
      draftSavedNoticeVisible = true
    }, delay)
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
    const username = currentPost.author?.username || ''
    if ($siteUser?.username && username === $siteUser.username) {
      return SITE_AUTHOR_CHOICE
    }
    const channelOption = publishIdentityOptions.find(
      (item) => item.kind === 'channel' && item.username === username
    )
    if (channelOption) return channelOption.value
    if ($siteUser?.authors?.length) {
      return `channel:${$siteUser.authors[0]?.username || ''}`
    }
    return SITE_AUTHOR_CHOICE
  }

  const fillForm = (currentPost: SiteUserPost) => {
    editTitle = currentPost.title || ''
    editContent = currentPost.content || ''
    editRubric = currentPost.rubric_slug || ''
    editAuthor = resolveAuthorValue(currentPost)
    editMovieReviewData = createEmptyMovieReviewTemplateData()
    editPostVotePollData = createEmptyPostVotePollTemplateData()
    editMusicReleaseData = createEmptyMusicReleaseTemplateData()
    editTemplateType =
      currentPost.template?.type === 'movie_review' ||
      currentPost.template?.type === 'post_vote_poll' ||
      currentPost.template?.type === 'music_release'
        ? currentPost.template.type
        : ''
    if (isMovieReviewTemplate(currentPost.template)) {
      editMovieReviewData = normalizeMovieReviewTemplateData(currentPost.template.data)
    } else if (isPostVotePollTemplate(currentPost.template)) {
      editPostVotePollData = normalizePostVotePollTemplateData(currentPost.template.data)
    } else if (isMusicReleaseTemplate(currentPost.template)) {
      editMusicReleaseData = normalizeMusicReleaseTemplateData(currentPost.template.data)
    }
    const tagNames = (currentPost.tags ?? []).map((tag) =>
      typeof tag === 'string' ? tag : tag.name
    )
    editTags = tagNames.join(', ')
    isJsonContent = detectContentType(editContent)
    lastObservedEditSnapshot = JSON.stringify(buildEditPayload())
    draftSavedNoticeVisible = false
    clearDraftSavedNoticeTimer()
    firstDraftChangeAt = null
    firstDraftAutosaveCompleted = false
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
    } catch {
      rubrics = []
    } finally {
      rubricsLoading = false
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
      await loadRubrics()
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
      let needsAnotherSave = false
      try {
        const updated = await updateUserPost(postId, {
          ...buildEditPayload(),
          is_draft: true,
        })
        post = updated
        const latestSnapshot = JSON.stringify(buildEditPayload())
        needsAnotherSave = latestSnapshot !== sentSnapshot
        lastObservedEditSnapshot = latestSnapshot
        if (!firstDraftAutosaveCompleted) {
          firstDraftAutosaveCompleted = true
          scheduleDraftSavedNotice()
        }
      } catch (err) {
        saveError = (err as Error)?.message ?? 'Не удалось сохранить черновик'
      } finally {
        autosaving = false
        if (needsAnotherSave) {
          queueDraftAutosave()
        }
      }
    }, 900)
  }

  const validateForPublish = () => {
    if (!editTitle.trim()) {
      saveError = 'Укажите заголовок поста'
      return false
    }
    const trimmedContent = editContent.trim()
    if (isJsonContent) {
      if (!trimmedContent) {
        saveError = 'Текст поста не может быть пустым'
        return false
      }
    } else if (stripHtml(trimmedContent).length === 0) {
      saveError = 'Текст поста не может быть пустым'
      return false
    }
    if (!editRubric) {
      saveError = 'Выберите рубрику'
      return false
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

  const selectRubric = (slug: string) => {
    editRubric = slug
    rubricMenuOpen = false
  }

  onMount(() => {
    loadPost()

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

  onDestroy(() => {
    clearAutosaveTimeout()
    clearDraftSavedNoticeTimer()
  })

  $: if (post?.is_draft && !editRubric && selectedChannelIdentity?.rubric_slug) {
    const authorRubric = selectedChannelIdentity.rubric_slug || ''
    if (authorRubric) editRubric = authorRubric
  }

  $: currentEditSnapshot = JSON.stringify(buildEditPayload())
  $: if (autosavePrimed && post?.is_draft && currentEditSnapshot !== lastObservedEditSnapshot) {
    if (!firstDraftChangeAt) firstDraftChangeAt = Date.now()
    lastObservedEditSnapshot = currentEditSnapshot
    queueDraftAutosave()
  }
</script>

<div class="flex flex-col gap-6 max-w-4xl">
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
    {#if draftSavedNoticeVisible && post.is_draft}
      <div class="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-900/20 dark:text-emerald-200">
        Материал сохранен как черновик, дальнейшее сохранение идет автоматически.
        Все черновики <a href={profileDraftsPath} class="underline decoration-emerald-500/70 underline-offset-2 hover:text-emerald-700 dark:hover:text-emerald-100">в профиле</a>.
      </div>
    {/if}
    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-4 sm:p-6 flex flex-col gap-4">
      {#if publishIdentityOptions.length > 1}
        <label class="flex flex-col gap-1 w-full">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Публиковать от имени</span>
          <select
            bind:value={editAuthor}
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
                    editRubric === rubric.slug ? 'bg-slate-100 dark:bg-zinc-800' : ''
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

      <TextInput label="Заголовок" bind:value={editTitle} />
      <TextInput label="Теги (через запятую)" bind:value={editTags} />
      <PostTemplateFields
        bind:templateType={editTemplateType}
        bind:movieReviewData={editMovieReviewData}
        bind:postVotePollData={editPostVotePollData}
        bind:musicReleaseData={editMusicReleaseData}
        {allowedTemplateTypes}
      />

      <div class="flex flex-col gap-2">
        {#if isJsonContent}
          {#key `edit-editor-template-${editorTemplateBlocksKey}`}
            <EditorJS
              bind:value={editContent}
              placeholder="Текст поста"
              postTemplateType={editTemplateType}
              enabledTemplateEditorBlockTypes={editorEnabledTemplateBlockTypes}
              enableAutosave={false}
              postId={post.id}
              showPostSettings={false}
            />
          {/key}
        {:else}
          <TipTapEditor
            bind:value={editContent}
            placeholder="Текст поста"
            includeMetaTags={false}
            allowMedia={false}
          />
        {/if}
      </div>

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
            Скопировать ссылку
          </Button>
          {#if draftSharePath}
            <Button color="ghost" href={draftSharePath} target="_blank" rel="noreferrer" disabled={publishing}>
              Открыть просмотр
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
        {/if}
        <Button color="ghost" href="/settings" disabled={saving || publishing}>
          Назад к настройкам
        </Button>
      </div>
    </div>
  {/if}
</div>
