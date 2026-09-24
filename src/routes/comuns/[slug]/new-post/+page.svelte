<script lang="ts">
  let imageUploadPending = false
  import PublishSchedule from '$lib/components/editor/PublishSchedule.svelte'
  import { scheduleError } from '$lib/postSchedule'
  let publishAt: string | null = null

  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Spinner, TextInput, toast } from 'mono-svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import GlossaryAutoLinkModal from '$lib/components/editor/GlossaryAutoLinkModal.svelte'
  import { deserializeEditorModel, postPayloadContainsExternalLinks } from '$lib/util'
  import {
    applyGlossaryAutoLinkMatches,
    findGlossaryAutoLinkMatches,
    type GlossaryAutoLinkMatch,
    type GlossaryAutoLinkTerm,
  } from '$lib/glossaryAutoLink'
  import {
    buildComunUrl,
    type BackendComun,
  } from '$lib/api/backend'
  import { createComunPost, refreshSiteUser, siteToken, siteUser } from '$lib/siteAuth'
  import { onMount } from 'svelte'
  import PostTemplateFields from '$lib/components/site/post-templates/PostTemplateFields.svelte'
  import {
    buildPostTemplatePayload,
    createEmptyBugReportTemplateData,
    createEmptyEventTemplateData,
    createEmptyCompanionTemplateData,
    validateCompanionTemplate,
    type CompanionTemplateData,
    createEmptyMusicReleaseTemplateData,
    createEmptyMovieReviewTemplateData,
    createEmptyPostVotePollTemplateData,
    normalizeAllowedPostTemplateTypeOverrides,
    normalizeAllowedPostTemplateTypes,
    normalizePostTemplateTypeOptions,
    normalizeTemplateEditorBlockSettings,
    resolveEnabledTemplateEditorBlockTypes,
    type BugReportTemplateData,
    type EventTemplateData,
    type MusicReleaseTemplateData,
    type MovieReviewTemplateData,
    type PostVotePollTemplateData,
    type PostTemplateType,
    type PostTemplateTypeOption,
    type TemplateEditorBlockSettings,
  } from '$lib/postTemplates'

  export let data

  let comun: BackendComun | null = data.comun ?? null
  let loadingUser = true
  let loadingComunAccess = false
  let authCheckDone = false

  let createTitle = ''
  let createContent = ''
  let createCategoryId = ''
  let creating = false
  let createError = ''
  let comunCategories: NonNullable<BackendComun['categories']> = []
  let createCategoryAutofilledFromQuery = false
  let createTemplateType: '' | PostTemplateType = ''
  let createMovieReviewData: MovieReviewTemplateData = createEmptyMovieReviewTemplateData()
  let createPostVotePollData: PostVotePollTemplateData = createEmptyPostVotePollTemplateData()
  let createMusicReleaseData: MusicReleaseTemplateData = createEmptyMusicReleaseTemplateData()
  let createBugReportData: BugReportTemplateData = createEmptyBugReportTemplateData()
  let createCompanionData: CompanionTemplateData = createEmptyCompanionTemplateData()
  let createEventData: EventTemplateData = createEmptyEventTemplateData()
  let comunAllowedTemplateTypes: string[] = ['basic']
  let templateTypeOptions: PostTemplateTypeOption[] = []
  let templateEditorBlockSettings: TemplateEditorBlockSettings = {}
  let editorEnabledTemplateBlockTypes: string[] = []
  let editorTemplateBlocksKey = 'basic:'
  let glossaryAutoLinkOpen = false
  let glossaryAutoLinkMatches: GlossaryAutoLinkMatch[] = []
  let pendingGlossaryCreate: PendingCreatePost | null = null

  type CreateComunPostPayload = {
    publish_at?: string | null
    title: string
    content: string
    author_source: 'site'
    comun_category_id: number | null
    template?: ReturnType<typeof buildPostTemplatePayload>
  }

  type PendingCreatePost = {
    payload: CreateComunPostPayload
    terms: GlossaryAutoLinkTerm[]
  }

  const isEditorContentEmpty = (value: string) => {
    if (!value || value.trim() === '') return true
    try {
      const parsed = deserializeEditorModel(value)
      return !parsed?.blocks || parsed.blocks.length === 0
    } catch {
      return true
    }
  }

  const normalizeCategoryQueryToken = (value?: string | null) =>
    (value ?? '')
      .toLowerCase()
      .replace(/[_\s]+/g, '-')
      .replace(/-+/g, '-')
      .trim()

  const formatRatingValue = (value?: number | null) => {
    const normalized = Math.max(Number(value ?? 0) || 0, 0)
    return new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(normalized)
  }

  const refreshComunAccess = async () => {
    if (!comun?.slug || !$siteToken) {
      authCheckDone = true
      return
    }
    loadingComunAccess = true
    try {
      const comunUrl = new URL(buildComunUrl(comun.slug), window.location.origin)
      comunUrl.searchParams.set('_', String(Date.now()))
      const response = await fetch(comunUrl.toString(), {
        headers: { Authorization: `Bearer ${$siteToken}` },
        cache: 'no-store',
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
  $: if (!createCategoryAutofilledFromQuery && comunCategories.length) {
    const queryCategoryId = Number($page.url.searchParams.get('comun_category_id') ?? 0)
    const queryCategory = normalizeCategoryQueryToken($page.url.searchParams.get('category'))
    let matchedCategory =
      queryCategoryId > 0 ? comunCategories.find((category) => Number(category.id) === queryCategoryId) : null
    if (!matchedCategory && queryCategory) {
      matchedCategory =
        comunCategories.find(
          (category) => normalizeCategoryQueryToken(category.slug) === queryCategory
        ) ??
        comunCategories.find(
          (category) => normalizeCategoryQueryToken(category.name) === queryCategory
        ) ??
        null
    }
    if (matchedCategory && !createCategoryId) {
      createCategoryId = String(matchedCategory.id)
    }
    createCategoryAutofilledFromQuery = true
  }
  $: minimumAuthorRatingToPost = Math.max(Number(comun?.minimum_author_rating_to_post ?? 0) || 0, 0)
  $: onlyModeratorsCanPost = Boolean(comun?.only_moderators_can_post)
  $: selectedComunCategory =
    comunCategories.find((category) => String(category.id) === createCategoryId) ?? null
  $: selectedCategoryOnlyModeratorsCanPost = Boolean(
    selectedComunCategory?.only_moderators_can_post
  )
  $: noCategoryOnlyModeratorsCanPost = Boolean(
    !createCategoryId && onlyModeratorsCanPost
  )
  $: selectedPlaceRestrictedForCurrentUser = Boolean(
    (noCategoryOnlyModeratorsCanPost || selectedCategoryOnlyModeratorsCanPost) && !comun?.can_moderate
  )
  $: canOpenComunEditor = Boolean(
    $siteToken && (comun?.can_post || comunCategories.length > 0)
  )
  $: selectedCategoryRestrictedForCurrentUser = Boolean(
    selectedCategoryOnlyModeratorsCanPost && !comun?.can_moderate
  )
  $: comunAllowedTemplateTypes = normalizeAllowedPostTemplateTypes(
    selectedComunCategory?.allowed_template_types ??
      (normalizeAllowedPostTemplateTypeOverrides(
        selectedComunCategory?.category_allowed_template_types
      ).length
        ? normalizeAllowedPostTemplateTypeOverrides(
            selectedComunCategory?.category_allowed_template_types
          )
        : comun?.allowed_template_types ?? comun?.allowed_post_templates)
  )
  $: templateEditorBlockSettings = normalizeTemplateEditorBlockSettings(
    comun?.options?.template_editor_blocks_by_template ?? comun?.template_editor_blocks_by_template
  )
  $: templateTypeOptions = normalizePostTemplateTypeOptions(
    comun?.options?.template_types ?? comun?.template_type_options
  )
  $: if (
    createTemplateType &&
    !comunAllowedTemplateTypes.includes(createTemplateType)
  ) {
    createTemplateType = ''
  }
  $: editorEnabledTemplateBlockTypes = Array.from(
    new Set([
      ...resolveEnabledTemplateEditorBlockTypes(createTemplateType, templateEditorBlockSettings),
    ])
  )
  $: editorTemplateBlocksKey = `${createTemplateType || 'basic'}:${editorEnabledTemplateBlockTypes.join(',')}`
  const glossaryAutoLinkTermsForComun = (targetComun: BackendComun | null) => {
    if (!targetComun?.glossary_enabled || !targetComun.glossary_auto_link_enabled) return []
    return (targetComun.glossary_terms ?? []) as GlossaryAutoLinkTerm[]
  }

  const mergeComunGlossaryFields = (
    baseComun: BackendComun | null,
    freshComun: BackendComun
  ): BackendComun => ({
    ...(baseComun ?? freshComun),
    glossary_enabled: Boolean(freshComun.glossary_enabled),
    glossary_auto_link_enabled: Boolean(freshComun.glossary_auto_link_enabled),
    glossary_terms: freshComun.glossary_terms ?? [],
    glossary_terms_count: freshComun.glossary_terms_count ?? freshComun.glossary_terms?.length ?? 0,
  })

  const loadFreshGlossaryComun = async (): Promise<BackendComun | null> => {
    if (!comun?.slug || !browser) return comun
    const fallbackComun = comun
    const headers: Record<string, string> = {}
    if ($siteToken) {
      headers.Authorization = `Bearer ${$siteToken}`
    }
    try {
      const comunUrl = new URL(buildComunUrl(comun.slug), window.location.origin)
      comunUrl.searchParams.set('_', String(Date.now()))
      const response = await fetch(comunUrl.toString(), {
        headers,
        cache: 'no-store',
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data?.comun) return fallbackComun
      const mergedComun = mergeComunGlossaryFields(fallbackComun, data.comun as BackendComun)
      comun = mergedComun
      return mergedComun
    } catch {
      return fallbackComun
    }
  }

  const loadGlossaryAutoLinkTermsForPublish = async () =>
    glossaryAutoLinkTermsForComun(await loadFreshGlossaryComun())

  const resetGlossaryAutoLinkPrompt = () => {
    glossaryAutoLinkOpen = false
    glossaryAutoLinkMatches = []
    pendingGlossaryCreate = null
  }

  const promptGlossaryAutoLinks = (pending: PendingCreatePost) => {
    const matches = findGlossaryAutoLinkMatches(pending.payload.content, pending.terms)
    if (!matches.length) return false
    pendingGlossaryCreate = pending
    glossaryAutoLinkMatches = matches
    glossaryAutoLinkOpen = true
    return true
  }

  const submitCreatePostPayload = async (pending: PendingCreatePost) => {
    if (!comun?.slug) return
    creating = true
    try {
      await createComunPost(comun.slug, pending.payload)
      toast({
        content: pending.payload.publish_at ? 'Публикация запланирована' : 'Пост опубликован в сообществе',
        type: 'success',
      })
      await goto(pending.payload.publish_at ? `/id${$siteUser?.id}?tab=drafts` : `/comuns/${comun.slug}`)
    } catch (error) {
      createError = (error as Error)?.message ?? 'Не удалось создать пост'
    } finally {
      creating = false
    }
  }

  const applyGlossaryAutoLinksAndCreate = async (ids: string[]) => {
    const pending = pendingGlossaryCreate
    if (!pending) return
    const nextPending = {
      ...pending,
      payload: {
        ...pending.payload,
        content: applyGlossaryAutoLinkMatches(pending.payload.content, pending.terms, ids),
      },
    }
    resetGlossaryAutoLinkPrompt()
    await submitCreatePostPayload(nextPending)
  }

  const createPost = async () => {
    if (imageUploadPending) return
    if (!$siteUser || !comun?.slug) return
    createError = scheduleError(publishAt)
    if (createError) return

    if (!canOpenComunEditor) {
      createError =
        noCategoryOnlyModeratorsCanPost
          ? 'Публикация без категории доступна только создателю и модераторам.'
          : minimumAuthorRatingToPost > 0
          ? `Публикация в этом сообществе доступна авторам с рейтингом от ${formatRatingValue(minimumAuthorRatingToPost)}.`
          : 'Сейчас вы не можете публиковать записи в это сообщество.'
      return
    }
    if (selectedPlaceRestrictedForCurrentUser) {
      createError = createCategoryId
        ? `Публикация в категории "${selectedComunCategory?.name ?? ''}" доступна только создателю и модераторам.`
        : 'Публикация без категории доступна только создателю и модераторам.'
      return
    }
    if (!createTitle.trim()) {
      createError = 'Укажите заголовок поста.'
      return
    }
    if (createTemplateType !== 'companion' && isEditorContentEmpty(createContent)) {
      createError = 'Текст поста не может быть пустым.'
      return
    }
    if (createTemplateType === 'companion') {
      createError = validateCompanionTemplate(createCompanionData, publishAt)
      if (createError) return
    }
    if (createTemplateType === 'event' && !createEventData.starts_at) {
      createError = 'Укажите дату и время события.'
      return
    }

    const template = buildPostTemplatePayload(
      createTemplateType,
      createMovieReviewData,
      createPostVotePollData,
      createMusicReleaseData,
      createBugReportData,
      createEventData,
      createCompanionData
    )
    if (
      comun?.forbid_external_links &&
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

    const pending: PendingCreatePost = {
      payload: {
        publish_at: publishAt,
        title: createTitle.trim(),
        content: createContent.trim(),
        author_source: 'site',
        comun_category_id: createCategoryId ? Number(createCategoryId) : null,
        template: template ?? undefined,
      },
      terms: await loadGlossaryAutoLinkTermsForPublish(),
    }
    if (pending.terms.length && promptGlossaryAutoLinks(pending)) return
    await submitCreatePostPayload(pending)
  }

  const goToLogin = () => {
    if (!comun?.slug) return
    goto(`/account?next=${encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)}`)
  }
</script>

<GlossaryAutoLinkModal
  open={glossaryAutoLinkOpen}
  matches={glossaryAutoLinkMatches}
  on:cancel={resetGlossaryAutoLinkPrompt}
  on:applyAll={() =>
    void applyGlossaryAutoLinksAndCreate(glossaryAutoLinkMatches.map((match) => match.id))}
  on:applySelected={(event) => void applyGlossaryAutoLinksAndCreate(event.detail.ids)}
/>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <div class="flex flex-wrap items-center justify-between gap-3 w-full">
      <div class="min-w-0">
        <h1 class="text-2xl font-bold">Новая запись в сообществе</h1>
        <div class="text-sm text-slate-600 dark:text-zinc-400">
          {#if comun?.name}
            {comun.name}
          {:else}
            Сообщество
          {/if}
        </div>
      </div>
      {#if comun?.slug}
        <Button color="ghost" on:click={() => goto(`/comuns/${comun?.slug ?? ''}`)}>
          Назад к сообществу
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
          Войдите, чтобы публиковать записи в сообществе.
        </p>
        <div>
          <Button on:click={goToLogin}>Войти</Button>
        </div>
      </div>
    {:else if authCheckDone && !canOpenComunEditor}
      <p class="text-sm text-slate-500 dark:text-zinc-400">
        {#if noCategoryOnlyModeratorsCanPost}
          Публикация без категории доступна только создателю и модераторам.
        {:else if minimumAuthorRatingToPost > 0}
          Публикация в этом сообществе доступна авторам с рейтингом от
          {formatRatingValue(minimumAuthorRatingToPost)}.
        {:else}
          Сейчас вы не можете публиковать записи в это сообщество.
        {/if}
      </p>
    {:else}
      <div class="flex flex-col gap-4">
        {#if minimumAuthorRatingToPost > 0}
          <div class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
            Порог публикации: рейтинг автора от {formatRatingValue(minimumAuthorRatingToPost)}.
          </div>
        {/if}

        <div class="rounded-lg border border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-800/40 px-3 py-2 text-sm text-slate-700 dark:text-zinc-300">
          Запись будет автоматически привязана к этому сообществу.
        </div>

        {#if comun?.rules_text}
          {#key comun.slug}
            <details class="group rounded-lg border border-slate-200 bg-white px-3 py-3 dark:border-zinc-800 dark:bg-zinc-900">
              <summary class="flex cursor-pointer list-none items-center justify-between gap-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-zinc-500 [&::-webkit-details-marker]:hidden">
                <span>Правила сообщества</span>
                <svg
                  class="h-4 w-4 shrink-0 transition-transform group-open:rotate-180"
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
              </summary>
              <div class="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-700 dark:text-zinc-300">
                {comun.rules_text}
              </div>
            </details>
          {/key}
        {/if}

        {#if comunCategories.length}
          <label class="flex flex-col gap-1">
            <span class="text-sm text-slate-700 dark:text-zinc-300">Категория внутри сообщества</span>
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

        {#if selectedPlaceRestrictedForCurrentUser}
          <div class="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200">
            {#if selectedCategoryRestrictedForCurrentUser}
              В категории "{selectedComunCategory?.name}" писать могут только администраторы и модераторы сообщества.
            {:else}
              Без категории писать могут только администраторы и модераторы сообщества.
            {/if}
          </div>
        {/if}

        <TextInput label="Заголовок" bind:value={createTitle} />
        <PostTemplateFields
          bind:templateType={createTemplateType}
          bind:movieReviewData={createMovieReviewData}
          bind:postVotePollData={createPostVotePollData}
          bind:musicReleaseData={createMusicReleaseData}
          bind:bugReportData={createBugReportData}
          bind:eventData={createEventData}
          bind:companionData={createCompanionData}
          allowedTemplateTypes={comunAllowedTemplateTypes}
          {templateTypeOptions}
        />

        {#key `editor-template-${editorTemplateBlocksKey}`}
          <EditorJS
            bind:hasPendingUploads={imageUploadPending}
            bind:value={createContent}
            placeholder="Текст поста"
            postTemplateType={createTemplateType}
            enabledTemplateEditorBlockTypes={editorEnabledTemplateBlockTypes}
            glossaryTerms={comun?.glossary_enabled ? comun?.glossary_terms ?? [] : []}
            glossaryComunSlug={comun?.glossary_enabled ? comun.slug : ''}
            canManageGlossary={Boolean(comun?.glossary_enabled && comun?.can_moderate)}
            enableAutosave={false}
            postId={null}
            showPostSettings={false}
          />
        {/key}

        {#if createError}
          <p class="text-sm text-red-600">{createError}</p>
        {/if}

        <div class="flex flex-wrap gap-2">
          <Button
            color="primary"
            on:click={createPost}
            loading={creating}
            disabled={imageUploadPending || creating}
          >
            {publishAt ? 'Запланировать' : 'Опубликовать в сообщество'}
          </Button>
          <PublishSchedule bind:value={publishAt} disabled={imageUploadPending || creating} />
          <Button
            color="ghost"
            on:click={() => {
              publishAt = null
              createTitle = ''
              createContent = ''
              createCategoryId = ''
              createTemplateType = ''
              createMovieReviewData = createEmptyMovieReviewTemplateData()
              createPostVotePollData = createEmptyPostVotePollTemplateData()
              createMusicReleaseData = createEmptyMusicReleaseTemplateData()
              createBugReportData = createEmptyBugReportTemplateData()
              createCompanionData = createEmptyCompanionTemplateData()
              createEventData = createEmptyEventTemplateData()
              createError = ''
            }}
            disabled={imageUploadPending || creating}
          >
            Очистить
          </Button>
        </div>
      </div>
    {/if}
  </div>
</div>
