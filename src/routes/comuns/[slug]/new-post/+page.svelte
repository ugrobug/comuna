<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Spinner, TextInput, toast } from 'mono-svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import { deserializeEditorModel, postPayloadContainsExternalLinks } from '$lib/util'
  import {
    buildComunCustomTemplateEditorPath,
    buildComunUrl,
    type BackendComun,
    type BackendComunCustomTemplate,
  } from '$lib/api/backend'
  import { createComunPost, refreshSiteUser, siteToken, siteUser } from '$lib/siteAuth'
  import { onMount } from 'svelte'
  import PostTemplateFields from '$lib/components/site/post-templates/PostTemplateFields.svelte'
  import {
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
  let comunAllowedTemplateTypes: string[] = ['basic']
  let templateTypeOptions: PostTemplateTypeOption[] = []
  let templateEditorBlockSettings: TemplateEditorBlockSettings = {}
  let customTemplatePreview: BackendComunCustomTemplate | null = null
  let editorEnabledTemplateBlockTypes: string[] = []
  let editorTemplateBlocksKey = 'basic:'
  let customTemplatePreviewBlockTypes: string[] = []
  let customTemplatePreviewHeaderBlocks: NonNullable<BackendComunCustomTemplate['blocks']> = []
  let customTemplatePreviewBodyBlocks: NonNullable<BackendComunCustomTemplate['blocks']> = []
  let customTemplatePreviewFooterBlocks: NonNullable<BackendComunCustomTemplate['blocks']> = []
  let customTemplatePreviewHeaderFields: NonNullable<BackendComunCustomTemplate['fields']> = []
  let customTemplatePreviewBodyFields: NonNullable<BackendComunCustomTemplate['fields']> = []
  let customTemplatePreviewFooterFields: NonNullable<BackendComunCustomTemplate['fields']> = []
  let customTemplatePreviewEditorPath = ''

  const customTemplatePreviewStorageKey = (slug: string) => `comuna:custom-template-preview:${slug}`

  const normalizeCustomTemplatePreview = (
    template?: BackendComunCustomTemplate | null
  ): BackendComunCustomTemplate | null => {
    if (!template) return null
    return {
      id: Number(template.id) > 0 ? Number(template.id) : undefined,
      name: String(template.name ?? '').trim(),
      slug: String(template.slug ?? '').trim() || undefined,
      sort_order: Number(template.sort_order ?? 0) || 0,
      blocks: Array.isArray(template.blocks)
        ? template.blocks.map((block, index) => ({
            id: Number(block?.id) > 0 ? Number(block.id) : undefined,
            block_type: String(block?.block_type ?? '').trim(),
            placement: (String(block?.placement ?? '').trim() || 'available') as
              | 'available'
              | 'header'
              | 'footer',
            is_required: Boolean(block?.is_required),
            sort_order: Number(block?.sort_order ?? index) || index,
          }))
        : [],
      fields: Array.isArray(template.fields)
        ? template.fields.map((field, index) => ({
            id: Number(field?.id) > 0 ? Number(field.id) : undefined,
            key: String(field?.key ?? '').trim() || undefined,
            label: String(field?.label ?? '').trim(),
            field_type: (String(field?.field_type ?? '').trim() || 'text') as
              | 'text'
              | 'file'
              | 'select'
              | 'checkbox',
            placement: (String(field?.placement ?? '').trim() || 'header') as
              | 'available'
              | 'header'
              | 'footer',
            is_required: Boolean(field?.is_required),
            options: Array.isArray(field?.options)
              ? field.options.map((option) => String(option ?? '').trim()).filter(Boolean)
              : [],
            settings:
              field && typeof field.settings === 'object' && field.settings
                ? {
                    max_length: Number(field.settings.max_length) > 0 ? Number(field.settings.max_length) : undefined,
                    default_checked: Boolean(field.settings.default_checked),
                  }
                : {},
            sort_order: Number(field?.sort_order ?? index) || index,
          }))
        : [],
    }
  }

  const loadCustomTemplatePreview = () => {
    if (!browser) return
    if (!comun?.slug) {
      customTemplatePreview = null
      return
    }
    if ($page.url.searchParams.get('template_preview') !== '1') {
      customTemplatePreview = null
      customTemplatePreviewEditorPath = ''
      return
    }
    try {
      const raw = localStorage.getItem(customTemplatePreviewStorageKey(comun.slug))
      if (!raw) {
        customTemplatePreview = null
        customTemplatePreviewEditorPath = ''
        return
      }
      const parsed = JSON.parse(raw)
      customTemplatePreview = normalizeCustomTemplatePreview(parsed?.template ?? null)
      customTemplatePreviewEditorPath =
        typeof parsed?.editor_path === 'string' && parsed.editor_path.startsWith('/comuns/')
          ? parsed.editor_path
          : ''
    } catch {
      customTemplatePreview = null
      customTemplatePreviewEditorPath = ''
    }
  }

  const resolveCustomTemplatePreviewEditorPath = () => {
    if (customTemplatePreviewEditorPath) return customTemplatePreviewEditorPath
    if (!comun?.slug) return ''
    const templateRef =
      customTemplatePreview?.slug?.trim() ||
      (Number(customTemplatePreview?.id) > 0 ? String(customTemplatePreview?.id) : 'new')
    return buildComunCustomTemplateEditorPath(comun.slug, templateRef)
  }

  const resolveCustomTemplateBlockLabel = (blockType?: string | null) =>
    String(blockType ?? '')
      .trim()
      .split('_')
      .filter(Boolean)
      .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
      .join(' ') || 'Блок'

  const resolveCustomTemplateFieldTypeLabel = (fieldType?: string | null) => {
    if (fieldType === 'file') return 'Файл'
    if (fieldType === 'select') return 'Выбор'
    if (fieldType === 'checkbox') return 'Чекбокс'
    return 'Текст'
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
        loadCustomTemplatePreview()
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
  $: if (comun?.slug) {
    loadCustomTemplatePreview()
  }
  $: if (
    createTemplateType &&
    !comunAllowedTemplateTypes.includes(createTemplateType)
  ) {
    createTemplateType = ''
  }
  $: customTemplatePreviewBlockTypes = Array.from(
    new Set(
      (customTemplatePreview?.blocks ?? [])
        .filter((block) => block.placement === 'available')
        .map((block) => String(block.block_type ?? '').trim())
        .filter(Boolean)
    )
  )
  $: editorEnabledTemplateBlockTypes = Array.from(
    new Set([
      ...resolveEnabledTemplateEditorBlockTypes(createTemplateType, templateEditorBlockSettings),
      ...customTemplatePreviewBlockTypes,
    ])
  )
  $: editorTemplateBlocksKey = `${createTemplateType || 'basic'}:${editorEnabledTemplateBlockTypes.join(',')}`
  $: customTemplatePreviewHeaderBlocks =
    (customTemplatePreview?.blocks ?? []).filter((block) => block.placement === 'header') ?? []
  $: customTemplatePreviewBodyBlocks =
    (customTemplatePreview?.blocks ?? []).filter((block) => block.placement === 'available') ?? []
  $: customTemplatePreviewFooterBlocks =
    (customTemplatePreview?.blocks ?? []).filter((block) => block.placement === 'footer') ?? []
  $: customTemplatePreviewHeaderFields =
    (customTemplatePreview?.fields ?? []).filter((field) => field.placement === 'header') ?? []
  $: customTemplatePreviewBodyFields =
    (customTemplatePreview?.fields ?? []).filter((field) => field.placement === 'available') ?? []
  $: customTemplatePreviewFooterFields =
    (customTemplatePreview?.fields ?? []).filter((field) => field.placement === 'footer') ?? []

  const createPost = async () => {
    if (!$siteUser || !comun?.slug) return
    createError = ''

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
    if (isEditorContentEmpty(createContent)) {
      createError = 'Текст поста не может быть пустым.'
      return
    }

    const template = buildPostTemplatePayload(
      createTemplateType,
      createMovieReviewData,
      createPostVotePollData,
      createMusicReleaseData
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

    creating = true
    try {
      await createComunPost(comun.slug, {
        title: createTitle.trim(),
        content: createContent.trim(),
        author_source: 'site',
        comun_category_id: createCategoryId ? Number(createCategoryId) : null,
        template: template ?? undefined,
      })
      toast({
        content: 'Пост опубликован в сообществе',
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
    goto(`/account?next=${encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)}`)
  }
</script>

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
          <div class="rounded-lg border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-3">
            <div class="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-zinc-500">
              Правила сообщества
            </div>
            <div class="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-700 dark:text-zinc-300">
              {comun.rules_text}
            </div>
          </div>
        {/if}

        {#if customTemplatePreview}
          <div class="rounded-[28px] border border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.94))] p-5 shadow-sm dark:border-zinc-800 dark:bg-[linear-gradient(180deg,rgba(19,24,34,0.98),rgba(14,18,28,0.94))]">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div class="text-xs uppercase tracking-[0.2em] text-slate-500 dark:text-zinc-400">
                  Предпросмотр шаблона
                </div>
                <div class="mt-1 text-lg font-semibold text-slate-900 dark:text-zinc-100">
                  {customTemplatePreview.name?.trim() || 'Шаблон без названия'}
                </div>
                <div class="mt-1 text-sm text-slate-600 dark:text-zinc-300">
                  Редактор открыт в режиме предпросмотра структуры. Ниже видно, как собран header, тело и footer шаблона.
                </div>
              </div>
              <div class="flex flex-wrap gap-2">
                <Button
                  color="primary"
                  size="sm"
                  on:click={() => goto(resolveCustomTemplatePreviewEditorPath())}
                  disabled={!resolveCustomTemplatePreviewEditorPath()}
                >
                  Редактировать шаблон
                </Button>
                <Button color="ghost" size="sm" on:click={() => goto(`/comuns/${comun?.slug ?? ''}/settings`)}>
                  К настройкам
                </Button>
              </div>
            </div>

            <div class="mt-4 flex flex-col gap-4">
              <div class="rounded-[24px] border border-amber-200 bg-amber-50/85 px-4 py-4 dark:border-amber-900/40 dark:bg-amber-950/15">
                <div class="text-xs uppercase tracking-[0.18em] text-amber-700 dark:text-amber-200">Header</div>
                <div class="mt-3 flex flex-col gap-3">
                  {#if customTemplatePreviewHeaderBlocks.length}
                    <div class="flex flex-wrap gap-2">
                      {#each customTemplatePreviewHeaderBlocks as block}
                        <span class="rounded-2xl border border-amber-200 bg-white/90 px-3 py-2 text-sm font-medium text-slate-800 dark:border-amber-900/40 dark:bg-zinc-950/45 dark:text-zinc-100">
                          {resolveCustomTemplateBlockLabel(block.block_type)}
                        </span>
                      {/each}
                    </div>
                  {/if}
                  {#if customTemplatePreviewHeaderFields.length}
                    <div class="grid gap-3 md:grid-cols-2">
                      {#each customTemplatePreviewHeaderFields as field}
                        <div class="rounded-2xl border border-amber-200 bg-white/85 px-3 py-3 dark:border-amber-900/40 dark:bg-zinc-950/40">
                          <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">
                            {field.label?.trim() || 'Поле без названия'}
                          </div>
                          <div class="mt-1 text-xs uppercase tracking-[0.12em] text-slate-500 dark:text-zinc-400">
                            {resolveCustomTemplateFieldTypeLabel(field.field_type)}
                          </div>
                        </div>
                      {/each}
                    </div>
                  {/if}
                  {#if !customTemplatePreviewHeaderBlocks.length && !customTemplatePreviewHeaderFields.length}
                    <div class="rounded-2xl border border-dashed border-amber-300/70 px-3 py-4 text-sm text-slate-600 dark:border-amber-900/40 dark:text-zinc-300">
                      Header пустой
                    </div>
                  {/if}
                </div>
              </div>

              <div class="rounded-[24px] border border-sky-200 bg-sky-50/85 px-4 py-4 dark:border-sky-900/40 dark:bg-sky-950/15">
                <div class="text-xs uppercase tracking-[0.18em] text-sky-700 dark:text-sky-200">Текст</div>
                <div class="mt-3 flex flex-col gap-3">
                  {#if customTemplatePreviewBodyBlocks.length}
                    {#each customTemplatePreviewBodyBlocks as block}
                      <div class="rounded-2xl border border-sky-200 bg-white/90 px-4 py-4 dark:border-sky-900/40 dark:bg-zinc-950/45">
                        <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">
                          {resolveCustomTemplateBlockLabel(block.block_type)}
                        </div>
                        <div class="mt-1 text-sm text-slate-500 dark:text-zinc-400">
                          Этот блок доступен внутри текста в редакторе ниже.
                        </div>
                      </div>
                    {/each}
                  {/if}
                  {#if customTemplatePreviewBodyFields.length}
                    <div class="grid gap-3 md:grid-cols-2">
                      {#each customTemplatePreviewBodyFields as field}
                        <div class="rounded-2xl border border-sky-200 bg-white/85 px-3 py-3 dark:border-sky-900/40 dark:bg-zinc-950/40">
                          <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">
                            {field.label?.trim() || 'Поле без названия'}
                          </div>
                          <div class="mt-1 text-xs uppercase tracking-[0.12em] text-slate-500 dark:text-zinc-400">
                            {resolveCustomTemplateFieldTypeLabel(field.field_type)}
                          </div>
                        </div>
                      {/each}
                    </div>
                  {/if}
                  {#if !customTemplatePreviewBodyBlocks.length && !customTemplatePreviewBodyFields.length}
                    <div class="rounded-2xl border border-dashed border-sky-300/70 px-3 py-4 text-sm text-slate-600 dark:border-sky-900/40 dark:text-zinc-300">
                      Текстовая часть шаблона пустая
                    </div>
                  {/if}
                </div>
              </div>

              <div class="rounded-[24px] border border-emerald-200 bg-emerald-50/85 px-4 py-4 dark:border-emerald-900/40 dark:bg-emerald-950/15">
                <div class="text-xs uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-200">Footer</div>
                <div class="mt-3 flex flex-col gap-3">
                  {#if customTemplatePreviewFooterBlocks.length}
                    <div class="flex flex-wrap gap-2">
                      {#each customTemplatePreviewFooterBlocks as block}
                        <span class="rounded-2xl border border-emerald-200 bg-white/90 px-3 py-2 text-sm font-medium text-slate-800 dark:border-emerald-900/40 dark:bg-zinc-950/45 dark:text-zinc-100">
                          {resolveCustomTemplateBlockLabel(block.block_type)}
                        </span>
                      {/each}
                    </div>
                  {/if}
                  {#if customTemplatePreviewFooterFields.length}
                    <div class="grid gap-3 md:grid-cols-2">
                      {#each customTemplatePreviewFooterFields as field}
                        <div class="rounded-2xl border border-emerald-200 bg-white/85 px-3 py-3 dark:border-emerald-900/40 dark:bg-zinc-950/40">
                          <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">
                            {field.label?.trim() || 'Поле без названия'}
                          </div>
                          <div class="mt-1 text-xs uppercase tracking-[0.12em] text-slate-500 dark:text-zinc-400">
                            {resolveCustomTemplateFieldTypeLabel(field.field_type)}
                          </div>
                        </div>
                      {/each}
                    </div>
                  {/if}
                  {#if !customTemplatePreviewFooterBlocks.length && !customTemplatePreviewFooterFields.length}
                    <div class="rounded-2xl border border-dashed border-emerald-300/70 px-3 py-4 text-sm text-slate-600 dark:border-emerald-900/40 dark:text-zinc-300">
                      Footer пустой
                    </div>
                  {/if}
                </div>
              </div>
            </div>
          </div>
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
          allowedTemplateTypes={comunAllowedTemplateTypes}
          {templateTypeOptions}
        />

        {#key `editor-template-${editorTemplateBlocksKey}`}
          <EditorJS
            bind:value={createContent}
            placeholder="Текст поста"
            postTemplateType={createTemplateType}
            enabledTemplateEditorBlockTypes={editorEnabledTemplateBlockTypes}
            glossaryTerms={comun?.glossary_enabled ? comun?.glossary_terms ?? [] : []}
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
            disabled={creating}
          >
            Опубликовать в сообщество
          </Button>
          <Button
            color="ghost"
            on:click={() => {
              createTitle = ''
              createContent = ''
              createCategoryId = ''
              createTemplateType = ''
              createMovieReviewData = createEmptyMovieReviewTemplateData()
              createPostVotePollData = createEmptyPostVotePollTemplateData()
              createMusicReleaseData = createEmptyMusicReleaseTemplateData()
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
