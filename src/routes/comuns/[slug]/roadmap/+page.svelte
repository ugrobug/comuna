<script lang="ts">
  import { page } from '$app/stores'
  import { tick } from 'svelte'
  import { Button, toast } from 'mono-svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import {
    buildBackendPostPath,
    buildComunPostsUrl,
    buildComunUrl,
    type BackendComun,
    type BackendComunCategory,
    type BackendPost,
  } from '$lib/api/backend'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import { looksLikeSerializedEditorModel, parseSerializedEditorModel } from '$lib/util'
  import { env } from '$env/dynamic/public'

  export let data

  type CategoryCountRow = {
    category_id?: number | null
    slug?: string | null
    count?: number | null
  }

  type CategoryPreviewRow = {
    category_slug?: string | null
    posts?: BackendPost[]
    total_count?: number | null
    error?: string | null
  }

  type RoadmapStageKey = 'suggestions' | 'backlog' | 'planned' | 'in_progress' | 'released'

  type RoadmapStageDefinition = {
    key: RoadmapStageKey
    label: string
    shortLabel: string
    description: string
    exactSlugs: string[]
    slugKeywords: string[]
    nameKeywords: string[]
  }

  type RoadmapLane = {
    id: string
    key: RoadmapStageKey | 'custom'
    category: BackendComunCategory
    label: string
    shortLabel: string
    description: string
    count: number
    error: string | null
    posts: BackendPost[]
    totalCount: number | null
    isKnownStage: boolean
  }

  const KNOWN_STAGE_DEFINITIONS: RoadmapStageDefinition[] = [
    {
      key: 'suggestions',
      label: 'Идеи от пользователей',
      shortLabel: 'Идеи',
      description: 'Пожелания, гипотезы и feature requests от пользователей.',
      exactSlugs: ['feature-ideas', 'suggestions', 'ideas', 'feature-requests', 'requests'],
      slugKeywords: ['idea', 'suggest', 'request', 'feedback', 'feature'],
      nameKeywords: ['иде', 'предлож', 'запрос', 'фидбек', 'улучш'],
    },
    {
      key: 'backlog',
      label: 'Беклог',
      shortLabel: 'Беклог',
      description: 'Отобранные задачи и идеи, которые команда рассматривает и приоритизирует.',
      exactSlugs: ['backlog'],
      slugKeywords: ['backlog', 'queue'],
      nameKeywords: ['беклог', 'очеред', 'приорит'],
    },
    {
      key: 'planned',
      label: 'Запланировано',
      shortLabel: 'План',
      description: 'То, что команда собирается делать следующим шагом.',
      exactSlugs: ['planned', 'plan', 'next', 'up-next', 'next-up'],
      slugKeywords: ['plan', 'planned', 'next'],
      nameKeywords: ['план', 'заплан', 'следующ', 'далее'],
    },
    {
      key: 'in_progress',
      label: 'В работе',
      shortLabel: 'В работе',
      description: 'Задачи, которые уже взяты в разработку.',
      exactSlugs: ['in-progress', 'in_progress', 'progress', 'doing', 'wip'],
      slugKeywords: ['progress', 'doing', 'wip', 'develop', 'active'],
      nameKeywords: ['в работе', 'разработ', 'делаем', 'делается'],
    },
    {
      key: 'released',
      label: 'Сделано / релизы',
      shortLabel: 'Готово',
      description: 'Изменения, которые уже доставлены пользователям.',
      exactSlugs: ['done', 'completed', 'shipped', 'released', 'changelog'],
      slugKeywords: ['done', 'complete', 'ship', 'release', 'changelog', 'live'],
      nameKeywords: ['готов', 'сделан', 'релиз', 'выпущ'],
    },
  ]

  const ROADMAP_PREVIEW_LIMIT = Number(data?.previewLimit ?? 12) || 12

  let comun: BackendComun | null = data?.comun ?? null
  let categoryCounts: CategoryCountRow[] = Array.isArray(data?.categoryCounts) ? data.categoryCounts : []
  let categoryPreviews: CategoryPreviewRow[] = Array.isArray(data?.categoryPreviews)
    ? data.categoryPreviews
    : []
  let roadmapSettingsSaving = false
  let roadmapSettingsOpen = false
  let roadmapSettingsSection: HTMLElement | null = null
  let roadmapSettingsDraftIds = normalizeRoadmapCategoryIds(
    data?.roadmapCategoryIds ?? comun?.roadmap_category_ids
  )

  function normalizeRoadmapCategoryIds(value: unknown) {
    const values = Array.isArray(value) ? value : []
    return Array.from(
      new Set(
        values
          .map((item) => Number(item))
          .filter((item) => Number.isFinite(item) && item > 0)
      )
    )
  }

  const normalizeToken = (value?: string | null) =>
    (value ?? '')
      .toLowerCase()
      .replace(/[_\s]+/g, '-')
      .replace(/-+/g, '-')
      .trim()

  const normalizeText = (value?: string | null) =>
    (value ?? '')
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim()

  const countFormat = (value?: number | null) =>
    new Intl.NumberFormat('ru-RU').format(Math.max(Number(value ?? 0) || 0, 0))

  const dateFormat = (value?: string | null) => {
    if (!value) return ''
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return ''
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: 'short',
    }).format(parsed)
  }

  const stripHtml = (value?: string | null) =>
    (value ?? '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&nbsp;/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()

  const truncateText = (value: string, maxLength: number) => {
    const text = value.replace(/\s+/g, ' ').trim()
    if (!text) return ''
    if (text.length <= maxLength) return text
    return `${text.slice(0, maxLength - 1).trimEnd()}…`
  }

  const textFromEditorBlock = (block: any) => {
    const type = String(block?.type ?? '').toLowerCase()
    const data = block?.data ?? {}
    if (['paragraph', 'header', 'quote', 'warning'].includes(type)) {
      return stripHtml(String(data?.text ?? data?.message ?? ''))
    }
    if (type === 'list' && Array.isArray(data?.items)) {
      return data.items.map((item: unknown) => stripHtml(String(item ?? ''))).filter(Boolean).join(' ')
    }
    if (type === 'checklist' && Array.isArray(data?.items)) {
      return data.items
        .map((item: any) => stripHtml(String(item?.text ?? '')))
        .filter(Boolean)
        .join(' ')
    }
    return ''
  }

  const editorSnippet = (raw: string, maxLength: number) => {
    const payload = parseSerializedEditorModel(raw)
    if (!payload) return ''

    const additional = payload?.additional ?? {}
    const description = stripHtml(
      String(additional?.metaDescription || additional?.previewDescription || '')
    )
    if (description) return truncateText(description, maxLength)

    const blocks = Array.isArray(payload?.blocks) ? payload.blocks : []
    for (const block of blocks) {
      const text = textFromEditorBlock(block)
      if (text) return truncateText(text, maxLength)
    }
    return ''
  }

  const snippet = (post: BackendPost, maxLength = 180) => {
    const raw = String(post.content ?? '').trim()
    if (!raw) return ''
    const editorText = editorSnippet(raw, maxLength)
    if (editorText) return editorText
    if (looksLikeSerializedEditorModel(raw)) return ''
    return truncateText(stripHtml(raw), maxLength)
  }

  const previewScore = (post: BackendPost) =>
    Number(post.likes_count ?? 0) * 3 +
    Number(post.comments_count ?? 0) * 5 +
    Number(post.views_count ?? 0) * 0.02

  const sortPreviewPosts = (posts: BackendPost[]) =>
    [...posts]
      .sort((a, b) => {
        const scoreDiff = previewScore(b) - previewScore(a)
        if (scoreDiff !== 0) return scoreDiff
        return String(b.created_at ?? '').localeCompare(String(a.created_at ?? ''))
      })
      .slice(0, ROADMAP_PREVIEW_LIMIT)

  const scoreCandidate = (
    stage: RoadmapStageDefinition,
    category: BackendComunCategory
  ) => {
    const slug = normalizeToken(category.slug)
    const name = normalizeText(category.name)
    if (!slug && !name) return 0
    if (stage.exactSlugs.includes(slug)) return 100
    let score = 0
    if (stage.key === 'suggestions' && ['suggestions', 'feature-ideas'].includes(slug)) {
      score = Math.max(score, 95)
    }
    if (stage.slugKeywords.some((keyword) => slug.includes(keyword))) score = Math.max(score, 70)
    if (stage.nameKeywords.some((keyword) => name.includes(keyword))) score = Math.max(score, 60)
    return score
  }

  const stageStyleVars = (key: RoadmapLane['key']) => {
    switch (key) {
      case 'suggestions':
        return '--lane-h: 201; --lane-s: 88%; --lane-l: 47%;'
      case 'backlog':
        return '--lane-h: 262; --lane-s: 72%; --lane-l: 52%;'
      case 'planned':
        return '--lane-h: 34; --lane-s: 88%; --lane-l: 50%;'
      case 'in_progress':
        return '--lane-h: 153; --lane-s: 77%; --lane-l: 40%;'
      case 'released':
        return '--lane-h: 340; --lane-s: 78%; --lane-l: 52%;'
      default:
        return '--lane-h: 220; --lane-s: 72%; --lane-l: 52%;'
    }
  }

  const laneStateLabel = (lane: RoadmapLane) => {
    switch (lane.key) {
      case 'suggestions':
        return 'Собираем'
      case 'backlog':
        return 'Приоритет'
      case 'planned':
        return 'Дальше'
      case 'in_progress':
        return 'В работе'
      case 'released':
        return 'Готово'
      default:
        return 'Этап'
    }
  }

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  const fetchRoadmapCategoryPreview = async (category: BackendComunCategory) => {
    const categorySlug = String(category?.slug ?? '').trim()
    if (!comun?.slug || !categorySlug) return null
    try {
      const previewUrl = new URL(
        buildComunPostsUrl(comun.slug, { categorySlug }),
        $page.url.origin
      )
      previewUrl.searchParams.set('limit', String(ROADMAP_PREVIEW_LIMIT))
      previewUrl.searchParams.set('offset', '0')
      const response = await fetch(previewUrl.toString())
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        return {
          category_slug: categorySlug,
          posts: [],
          total_count: null,
          error: String(payload?.error || 'Не удалось загрузить превью'),
        }
      }
      return {
        category_slug: categorySlug,
        posts: payload?.posts ?? [],
        total_count:
          typeof payload?.total_count === 'number' ? Number(payload.total_count) : null,
        error: null,
      }
    } catch (error) {
      return {
        category_slug: categorySlug,
        posts: [],
        total_count: null,
        error: error instanceof Error ? error.message : 'Ошибка загрузки',
      }
    }
  }

  const refreshRoadmapPreviews = async (nextComun: BackendComun | null) => {
    const selectedIds = new Set(normalizeRoadmapCategoryIds(nextComun?.roadmap_category_ids))
    const nextCategories = (nextComun?.categories ?? []).filter((category) =>
      selectedIds.has(Number(category.id))
    )
    categoryPreviews = (await Promise.all(nextCategories.map(fetchRoadmapCategoryPreview))).filter(
      Boolean
    ) as CategoryPreviewRow[]
  }

  const toggleRoadmapSettingsCategory = (categoryId: number) => {
    const next = new Set(roadmapSettingsDraftIds)
    if (next.has(categoryId)) {
      next.delete(categoryId)
    } else {
      next.add(categoryId)
    }
    roadmapSettingsDraftIds = Array.from(next)
  }

  const saveRoadmapSettings = async () => {
    if (!comun?.slug || roadmapSettingsSaving) return
    roadmapSettingsSaving = true
    try {
      const response = await fetch(buildComunUrl(comun.slug), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({
          roadmap_category_ids: roadmapSettingsDraftIds,
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось сохранить настройки дорожной карты')
      }
      comun = payload.comun ?? comun
      roadmapSettingsDraftIds = normalizeRoadmapCategoryIds(comun?.roadmap_category_ids)
      await refreshRoadmapPreviews(comun)
      if (roadmapSettingsDraftIds.length > 0) {
        roadmapSettingsOpen = false
      }
      toast({ content: 'Настройки дорожной карты сохранены', type: 'success' })
    } catch (error) {
      toast({
        content: error instanceof Error ? error.message : 'Ошибка сохранения',
        type: 'error',
      })
    } finally {
      roadmapSettingsSaving = false
    }
  }

  const openRoadmapSettings = async () => {
    roadmapSettingsOpen = true
    await tick()
    roadmapSettingsSection?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  $: allCategories = Array.isArray(comun?.categories) ? (comun?.categories ?? []) : []
  $: savedRoadmapCategoryIds = new Set(normalizeRoadmapCategoryIds(comun?.roadmap_category_ids))
  $: categories = allCategories.filter((category) => savedRoadmapCategoryIds.has(Number(category.id)))
  $: roadmapSettingsHasChanges =
    JSON.stringify([...roadmapSettingsDraftIds].sort((a, b) => a - b)) !==
    JSON.stringify([...savedRoadmapCategoryIds].sort((a, b) => a - b))
  $: countByCategoryId = new Map<number, number>(
    categoryCounts
      .map((row) => [Number(row?.category_id ?? 0), Math.max(Number(row?.count ?? 0) || 0, 0)] as const)
      .filter(([id]) => id > 0)
  )
  $: previewBySlug = new Map<string, CategoryPreviewRow>(
    categoryPreviews
      .map((row) => [String(row?.category_slug ?? '').trim(), row] as const)
      .filter(([slug]) => Boolean(slug))
  )

  $: usedCategoryIds = new Set<number>()
  $: knownStageLanes = KNOWN_STAGE_DEFINITIONS.map((stage) => {
    const candidate = categories
      .filter((category) => !usedCategoryIds.has(category.id))
      .map((category) => ({ category, score: scoreCandidate(stage, category) }))
      .filter((item) => item.score > 0)
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        return (
          Number(a.category.sort_order ?? 0) - Number(b.category.sort_order ?? 0) ||
          a.category.name.localeCompare(b.category.name, 'ru')
        )
      })[0]
    if (!candidate) return null
    usedCategoryIds.add(candidate.category.id)
    const preview = previewBySlug.get(candidate.category.slug)
    return {
      id: `${stage.key}:${candidate.category.id}`,
      key: stage.key,
      category: candidate.category,
      label: stage.label,
      shortLabel: stage.shortLabel,
      description: stage.description,
      count: Math.max(countByCategoryId.get(candidate.category.id) ?? 0, 0),
      error: (preview?.error as string | null) ?? null,
      posts: sortPreviewPosts((preview?.posts ?? []) as BackendPost[]),
      totalCount: typeof preview?.total_count === 'number' ? Number(preview.total_count) : null,
      isKnownStage: true,
    } satisfies RoadmapLane
  }).filter(Boolean) as RoadmapLane[]

  $: extraLanes = categories
    .filter((category) => !usedCategoryIds.has(category.id))
    .sort(
      (a, b) =>
        Number(a.sort_order ?? 0) - Number(b.sort_order ?? 0) ||
        a.name.localeCompare(b.name, 'ru')
    )
    .map((category) => {
      const preview = previewBySlug.get(category.slug)
      return {
        id: `custom:${category.id}`,
        key: 'custom',
        category,
        label: category.name,
        shortLabel: category.name,
        description:
          category.description?.trim() ||
          'Отдельный этап/срез в вашей публичной дорожной карте.',
        count: Math.max(countByCategoryId.get(category.id) ?? 0, 0),
        error: (preview?.error as string | null) ?? null,
        posts: sortPreviewPosts((preview?.posts ?? []) as BackendPost[]),
        totalCount: typeof preview?.total_count === 'number' ? Number(preview.total_count) : null,
        isKnownStage: false,
      } satisfies RoadmapLane
  })

  $: roadmapLanes = [...knownStageLanes, ...extraLanes]
  $: selectedCategorySlug = String($page.url.searchParams.get('category') || '').trim()
  $: highlightedLane = roadmapLanes.find((lane) => lane.category.slug === selectedCategorySlug) ?? null
  $: currentUserId = Number($siteUser?.id ?? 0)
  $: canManageRoadmap = Boolean(
    $siteToken &&
      currentUserId > 0 &&
      (Number(comun?.creator?.id ?? 0) === currentUserId ||
        (comun?.moderators ?? []).some(
          (moderator) => Number(moderator?.id ?? 0) === currentUserId
        ) ||
        comun?.can_moderate)
  )
  $: showRoadmapSettings =
    canManageRoadmap && (savedRoadmapCategoryIds.size === 0 || roadmapSettingsOpen)
  $: comunName = comun?.name || 'Сообщество'
  $: pageTitle = `Публичная дорожная карта — ${comunName}`
  $: pageDescription =
    comun?.product_description?.trim() ||
    `Публичная дорожная карта и беклог продукта «${comunName}»: что планируется дальше и что обсуждают пользователи.`
  $: canonicalUrl = new URL(
    $page.url.pathname + ($page.url.search || ''),
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()
</script>

<div class="mx-auto flex w-full max-w-7xl flex-col gap-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="min-w-0">
      <Header noMargin>Публичная дорожная карта</Header>
      {#if comun?.name}
        <div class="truncate text-sm text-slate-600 dark:text-zinc-400">{comun.name}</div>
      {/if}
      {#if highlightedLane}
        <div class="mt-2">
          <span class="filter-pill" style={stageStyleVars(highlightedLane.key)}>
            Фильтр: {highlightedLane.shortLabel}
          </span>
        </div>
      {/if}
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <a
        href={comun?.slug ? `/comuns/${encodeURIComponent(comun.slug)}` : '/comuns'}
        class="inline-flex items-center rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-900 transition hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-800/60"
      >
        Назад к сообществу
      </a>
      {#if canManageRoadmap}
        <button
          type="button"
          on:click={openRoadmapSettings}
          class="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 text-slate-900 transition hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-800/60"
          aria-label="Настройки дорожной карты"
          title="Настройки дорожной карты"
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
            class="h-5 w-5"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
            <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.04.04a2.05 2.05 0 0 1-2.9 2.9l-.04-.04A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21a2.05 2.05 0 0 1-4.1 0v-.06A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.04.04a2.05 2.05 0 0 1-2.9-2.9l.04-.04A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3a2.05 2.05 0 0 1 0-4.1h.06A1.7 1.7 0 0 0 4.6 8.6a1.7 1.7 0 0 0-.34-1.88l-.04-.04a2.05 2.05 0 0 1 2.9-2.9l.04.04A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3a2.05 2.05 0 0 1 4.1 0v.06A1.7 1.7 0 0 0 15.4 4.6a1.7 1.7 0 0 0 1.88-.34l.04-.04a2.05 2.05 0 0 1 2.9 2.9l-.04.04A1.7 1.7 0 0 0 19.4 9c.4.2.75.4 1 .6.3.3.4.7.4 1.1V11a2.05 2.05 0 0 1 0 4.1h-.06a1.7 1.7 0 0 0-1.34.9Z" />
          </svg>
        </button>
      {/if}
    </div>
  </div>

  <section class="roadmap-page-shell overflow-hidden rounded-3xl">
    <div class="roadmap-page-glow"></div>
    <div class="roadmap-page-content relative z-10 flex flex-col gap-5 p-4 sm:p-5 lg:p-6">
      {#if showRoadmapSettings}
        <section
          id="roadmap-settings"
          bind:this={roadmapSettingsSection}
          class="roadmap-settings-card rounded-2xl p-4 sm:p-5"
        >
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div class="max-w-3xl">
              <div class="text-sm font-semibold text-slate-900 dark:text-zinc-100">
                Настройки дорожной карты
              </div>
              <p class="mt-1 text-sm text-slate-600 dark:text-zinc-400">
                Выберите категории сообщества, из которых посты будут отображаться в публичной дорожной карте.
                Лучше всего сделать категорию «Предложения пользователей» для идей и категорию «Беклог»,
                где админы публикуют то, что взяли в работу.
              </p>
            </div>
            <Button
              on:click={saveRoadmapSettings}
              disabled={roadmapSettingsSaving || !roadmapSettingsHasChanges}
            >
              {roadmapSettingsSaving ? 'Сохраняем...' : 'Сохранить настройки'}
            </Button>
          </div>

          {#if allCategories.length}
            <div class="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {#each allCategories as category}
                {@const categoryId = Number(category.id)}
                <label class="roadmap-category-option rounded-2xl p-3">
                  <input
                    type="checkbox"
                    class="mt-1"
                    checked={roadmapSettingsDraftIds.includes(categoryId)}
                    on:change={() => toggleRoadmapSettingsCategory(categoryId)}
                    disabled={roadmapSettingsSaving}
                  />
                  <span class="min-w-0">
                    <span class="block font-semibold text-slate-900 dark:text-zinc-100">
                      {category.name}
                    </span>
                    {#if category.description}
                      <span class="mt-1 block text-xs text-slate-500 dark:text-zinc-400">
                        {category.description}
                      </span>
                    {/if}
                  </span>
                </label>
              {/each}
            </div>
          {:else}
            <div class="mt-4 rounded-2xl border border-dashed border-slate-300 bg-white/60 p-4 text-sm text-slate-600 dark:border-zinc-700 dark:bg-zinc-900/35 dark:text-zinc-400">
              В сообществе пока нет категорий. Создайте категории в настройках сообщества, затем выберите их здесь для дорожной карты.
            </div>
          {/if}
        </section>
      {/if}

      {#if roadmapLanes.length}
        <div class="roadmap-grid">
          {#each roadmapLanes as lane}
            <section
              class="roadmap-lane rounded-2xl p-4"
              style={stageStyleVars(lane.key)}
              data-highlight={selectedCategorySlug === lane.category.slug ? '1' : '0'}
            >
              <div class="mb-3 flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="lane-pill">{laneStateLabel(lane)}</div>
                  <div class="mt-2 text-sm font-semibold text-slate-900 dark:text-zinc-100">
                    {lane.label}
                  </div>
                  <div class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
                    {countFormat(lane.count)} карточек
                    {#if lane.totalCount !== null && lane.totalCount !== lane.count}
                      · загружено {countFormat(lane.posts.length)} из {countFormat(lane.totalCount)}
                    {/if}
                  </div>
                </div>
                <a href={`/comuns/${comun?.slug ?? ''}?category=${encodeURIComponent(lane.category.slug)}`} class="lane-link">
                  Открыть
                </a>
              </div>

              <p class="lane-description">{lane.description}</p>

              {#if lane.error}
                <div class="lane-state lane-state--error">{lane.error}</div>
              {:else if lane.posts.length}
                <div class="mt-3 flex flex-col gap-2">
                  {#each lane.posts as post}
                    {@const postSnippet = snippet(post)}
                    {@const postDate = dateFormat(post.created_at)}
                    <a href={buildBackendPostPath(post)} class="mini-card rounded-xl p-3">
                      <div class="mini-card__title">{post.title || 'Без заголовка'}</div>
                      {#if postSnippet}
                        <div class="mini-card__snippet">{postSnippet}</div>
                      {/if}
                      <div class="mini-card__meta">
                        <span>Голоса {countFormat(post.likes_count ?? 0)}</span>
                        <span>Комментарии {countFormat(post.comments_count ?? 0)}</span>
                        {#if postDate}
                          <span>{postDate}</span>
                        {/if}
                      </div>
                      <div class="mini-card__cta">
                        Открыть карточку и обсуждение
                      </div>
                    </a>
                  {/each}
                </div>
              {:else}
                <div class="lane-state">
                  В этой колонке пока нет карточек.
                </div>
              {/if}
            </section>
          {/each}
        </div>
      {:else}
        <section class="empty-roadmap rounded-2xl p-5">
          <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">
            Публичная дорожная карта пока не настроена
          </div>
          <div class="mt-2 text-sm text-slate-600 dark:text-zinc-400">
            {#if canManageRoadmap}
              Выберите категории выше, чтобы публикации из них появились в публичной дорожной карте.
            {:else}
              Администратор сообщества еще не выбрал категории для публичной дорожной карты.
            {/if}
          </div>
        </section>
      {/if}
    </div>
  </section>
</div>

<svelte:head>
  <title>{pageTitle}</title>
  <meta name="description" content={pageDescription} />
  <meta property="og:title" content={pageTitle} />
  <meta property="og:description" content={pageDescription} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  {#if comun?.logo_url}
    <meta property="og:image" content={comun.logo_url} />
    <meta name="twitter:image" content={comun.logo_url} />
    <meta name="twitter:card" content="summary_large_image" />
  {/if}
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>

<style>
  .roadmap-page-shell {
    position: relative;
    border: 1px solid rgba(148, 163, 184, 0.28);
    background:
      radial-gradient(circle at 12% 12%, rgba(59, 130, 246, 0.12), transparent 38%),
      radial-gradient(circle at 88% 8%, rgba(249, 115, 22, 0.12), transparent 34%),
      linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.95));
    box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
  }

  :global(.dark) .roadmap-page-shell {
    border-color: rgba(63, 63, 70, 0.9);
    background:
      radial-gradient(circle at 12% 12%, rgba(59, 130, 246, 0.18), transparent 38%),
      radial-gradient(circle at 88% 8%, rgba(249, 115, 22, 0.14), transparent 34%),
      linear-gradient(180deg, rgba(24, 24, 27, 0.96), rgba(10, 10, 11, 0.97));
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.34);
  }

  .roadmap-page-glow {
    position: absolute;
    inset: -4px;
    pointer-events: none;
    border-radius: 1.7rem;
    background: linear-gradient(
      125deg,
      rgba(59, 130, 246, 0.22),
      rgba(168, 85, 247, 0.14),
      rgba(16, 185, 129, 0.16)
    );
    filter: blur(24px);
    opacity: 0.4;
  }

  .roadmap-settings-card,
  .empty-roadmap {
    border: 1px solid rgba(148, 163, 184, 0.22);
    background: rgba(255, 255, 255, 0.78);
    backdrop-filter: blur(8px);
  }

  :global(.dark) .roadmap-settings-card,
  :global(.dark) .empty-roadmap {
    border-color: rgba(63, 63, 70, 0.85);
    background: rgba(24, 24, 27, 0.72);
  }

  .roadmap-category-option {
    display: flex;
    gap: 0.75rem;
    border: 1px solid rgba(148, 163, 184, 0.28);
    background: rgba(255, 255, 255, 0.72);
    cursor: pointer;
    transition:
      border-color 0.16s ease,
      background-color 0.16s ease,
      transform 0.16s ease;
  }

  .roadmap-category-option:hover {
    border-color: rgba(59, 130, 246, 0.38);
    background: rgba(239, 246, 255, 0.78);
    transform: translateY(-1px);
  }

  :global(.dark) .roadmap-category-option {
    border-color: rgba(63, 63, 70, 0.85);
    background: rgba(39, 39, 42, 0.58);
  }

  :global(.dark) .roadmap-category-option:hover {
    border-color: rgba(96, 165, 250, 0.42);
    background: rgba(30, 41, 59, 0.52);
  }

  .filter-pill {
    display: inline-flex;
    align-items: center;
    border-radius: 9999px;
    padding: 0.35rem 0.7rem;
    border: 1px solid hsla(var(--lane-h), 70%, 45%, 0.28);
    background: hsla(var(--lane-h), 92%, 95%, 0.9);
    color: hsl(var(--lane-h) 62% 28%);
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  :global(.dark) .filter-pill {
    border-color: hsla(var(--lane-h), 55%, 58%, 0.3);
    background: hsla(var(--lane-h), 44%, 18%, 0.55);
    color: hsl(var(--lane-h) 88% 82%);
  }

  .roadmap-grid {
    display: grid;
    gap: 0.9rem;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    align-items: start;
  }

  .roadmap-lane {
    border: 1px solid rgba(148, 163, 184, 0.22);
    background:
      linear-gradient(
        180deg,
        hsla(var(--lane-h), 95%, 97%, 0.84),
        rgba(255, 255, 255, 0.86)
      );
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }

  .roadmap-lane[data-highlight='1'] {
    border-color: hsla(var(--lane-h), 78%, 46%, 0.4);
    box-shadow: 0 0 0 1px hsla(var(--lane-h), 78%, 46%, 0.18) inset;
  }

  :global(.dark) .roadmap-lane {
    border-color: rgba(63, 63, 70, 0.85);
    background:
      linear-gradient(
        180deg,
        hsla(var(--lane-h), 44%, 15%, 0.4),
        rgba(24, 24, 27, 0.84)
      );
  }

  :global(.dark) .roadmap-lane[data-highlight='1'] {
    border-color: hsla(var(--lane-h), 72%, 56%, 0.42);
    box-shadow: 0 0 0 1px hsla(var(--lane-h), 72%, 56%, 0.2) inset;
  }

  .lane-pill {
    display: inline-flex;
    align-items: center;
    border-radius: 9999px;
    padding: 0.22rem 0.55rem;
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: hsl(var(--lane-h) 60% 30%);
    background: hsla(var(--lane-h), 92%, 93%, 0.94);
    border: 1px solid hsla(var(--lane-h), 84%, 56%, 0.2);
  }

  :global(.dark) .lane-pill {
    color: hsl(var(--lane-h) 88% 82%);
    background: hsla(var(--lane-h), 46%, 18%, 0.58);
    border-color: hsla(var(--lane-h), 62%, 52%, 0.22);
  }

  .lane-link {
    display: inline-flex;
    align-items: center;
    border-radius: 0.75rem;
    padding: 0.42rem 0.62rem;
    font-size: 0.78rem;
    font-weight: 600;
    color: rgb(30 64 175);
    background: rgba(239, 246, 255, 0.9);
    border: 1px solid rgba(96, 165, 250, 0.2);
  }

  :global(.dark) .lane-link {
    color: rgb(147 197 253);
    background: rgba(30, 41, 59, 0.78);
    border-color: rgba(59, 130, 246, 0.3);
  }

  .lane-description {
    margin: 0;
    color: rgb(71 85 105);
    font-size: 0.82rem;
    line-height: 1.4;
  }

  :global(.dark) .lane-description {
    color: rgb(161 161 170);
  }

  .mini-card {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    border: 1px solid rgba(148, 163, 184, 0.18);
    background: rgba(255, 255, 255, 0.86);
    transition:
      transform 0.14s ease,
      box-shadow 0.14s ease,
      border-color 0.14s ease;
  }

  .mini-card:hover {
    transform: translateY(-1px);
    border-color: hsla(var(--lane-h), 80%, 48%, 0.28);
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.07);
  }

  :global(.dark) .mini-card {
    border-color: rgba(63, 63, 70, 0.78);
    background: rgba(9, 9, 11, 0.36);
  }

  :global(.dark) .mini-card:hover {
    border-color: hsla(var(--lane-h), 70%, 56%, 0.3);
    box-shadow: 0 8px 18px rgba(0, 0, 0, 0.24);
  }

  .mini-card__title {
    line-clamp: 2;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-size: 0.88rem;
    line-height: 1.28;
    font-weight: 600;
    color: rgb(15 23 42);
  }

  .mini-card__snippet {
    line-clamp: 3;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-size: 0.78rem;
    line-height: 1.4;
    color: rgb(71 85 105);
  }

  .mini-card__meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.6rem;
    font-size: 0.72rem;
    color: rgb(100 116 139);
  }

  .mini-card__cta {
    font-size: 0.76rem;
    font-weight: 600;
    color: hsl(var(--lane-h) 62% 36%);
  }

  :global(.dark) .mini-card__title {
    color: rgb(244 244 245);
  }

  :global(.dark) .mini-card__snippet,
  :global(.dark) .mini-card__meta {
    color: rgb(161 161 170);
  }

  :global(.dark) .mini-card__cta {
    color: hsl(var(--lane-h) 90% 80%);
  }

  .lane-state {
    margin-top: 0.8rem;
    border-radius: 0.85rem;
    border: 1px dashed rgba(148, 163, 184, 0.28);
    background: rgba(248, 250, 252, 0.78);
    color: rgb(71 85 105);
    font-size: 0.82rem;
    line-height: 1.38;
    padding: 0.8rem;
  }

  .lane-state--error {
    border-color: rgba(244, 63, 94, 0.3);
    background: rgba(255, 241, 242, 0.84);
    color: rgb(159 18 57);
  }

  :global(.dark) .lane-state {
    border-color: rgba(82, 82, 91, 0.9);
    background: rgba(9, 9, 11, 0.34);
    color: rgb(212 212 216);
  }

  :global(.dark) .lane-state--error {
    border-color: rgba(190, 24, 93, 0.34);
    background: rgba(80, 7, 36, 0.3);
    color: rgb(253 164 175);
  }
</style>
