<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { onDestroy, onMount } from 'svelte'
  import { Button, Modal, toast } from 'mono-svelte'
  import Portal from '$lib/mono/popover/Portal.svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { feedKeyboardShortcuts } from '$lib/actions/feedKeyboardShortcuts'
  import {
    backendPostToPostView,
    buildBackendPostPath,
    buildComunPostCategoryUrl,
    buildComunPostsUrl,
    buildComunUrl,
    buildComunVoteUrl,
    buildTagsEnsureUrl,
    type BackendComun,
    type BackendComunCategory,
    type BackendPost,
    type BackendTag,
  } from '$lib/api/backend'
  import { refreshSiteUser, siteToken, siteUser, uploadSiteImage } from '$lib/siteAuth'
  import { env } from '$env/dynamic/public'
  import { userSettings } from '$lib/settings'
  import { deserializeEditorModel } from '$lib/util'

  export let data

  const pageSize = data.pageSize ?? 10
  let comun: BackendComun | null = data.comun ?? null
  let posts: BackendPost[] = data.posts ?? []
  let selectedCategorySlug = data.selectedCategory?.slug ?? data.initialCategorySlug ?? ''
  let hasMore = posts.length === pageSize
  let loadingMore = false
  let loadingCategory = false
  let lastPostsRef = data.posts
  let lastComunRef = data.comun
  const scrollThreshold = 400
  let scrollRaf: number | null = null
  let categorySavingPostIds = new Set<number>()
  let comunVoteSaving = false

  let settingsOpen = false
  let settingsLoading = false
  let settingsSaving = false
  let settingsLogoUploading = false
  let settingsError = ''
  let settingsTagSearch = ''
  let settingsTagCreating = false
  let settingsUserSearch = ''
  let settingsDraft: BackendComun | null = null
  let settingsLogoInput: HTMLInputElement | null = null
  let lastAuthRefreshToken: string | null = null
  let autoSettingsOpenHandled = false
  let wantsSettingsOpenFromUrl = false
  let settingsCategoryOptions: BackendComunCategory[] = []
  type ComunTagOption = BackendTag & { id: number }
  type ComunUserOption = { id: number; username: string; display_name?: string | null }
  let settingsTagOptions: ComunTagOption[] = []
  let settingsUserOptions: ComunUserOption[] = []
  const COMUN_SUGGESTIONS_CATEGORY_SLUGS = new Set(['feature-ideas', 'suggestions'])
  const COMUN_BACKLOG_CATEGORY_SLUG = 'backlog'
  const ROADMAP_PREVIEW_LIMIT = 4
  const ROADMAP_PREVIEW_FETCH_LIMIT = 8

  type ComunCategoryCount = {
    category_id?: number | null
    slug?: string | null
    count?: number | null
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
    emptyState: string
  }

  type RoadmapStage = RoadmapStageDefinition & {
    category: BackendComunCategory
    count: number
  }

  type RoadmapPreviewState = {
    loading: boolean
    error: string | null
    posts: BackendPost[]
  }

  const ROADMAP_STAGE_DEFINITIONS: RoadmapStageDefinition[] = [
    {
      key: 'suggestions',
      label: 'Идеи от пользователей',
      shortLabel: 'Идеи',
      description: 'Сюда попадают предложения и запросы на новые возможности.',
      exactSlugs: ['feature-ideas', 'suggestions', 'ideas', 'feature-requests', 'requests'],
      slugKeywords: ['idea', 'suggest', 'request', 'feedback', 'feature'],
      nameKeywords: ['иде', 'предлож', 'запрос', 'фидбек', 'улучш'],
      emptyState: 'Пока нет новых идей. Можно пригласить пользователей написать первый запрос.',
    },
    {
      key: 'backlog',
      label: 'Беклог',
      shortLabel: 'Беклог',
      description: 'Отобранные идеи, которые команда рассматривает и приоритизирует.',
      exactSlugs: ['backlog'],
      slugKeywords: ['backlog', 'queue'],
      nameKeywords: ['беклог', 'очеред', 'очередь', 'приорит'],
      emptyState: 'Беклог пока пуст. Перенесите сюда лучшие предложения из идей.',
    },
    {
      key: 'planned',
      label: 'Запланировано',
      shortLabel: 'План',
      description: 'Функции и изменения, которые команда собирается сделать дальше.',
      exactSlugs: ['planned', 'plan', 'next', 'up-next', 'next-up'],
      slugKeywords: ['plan', 'planned', 'next', 'up-next', 'queue'],
      nameKeywords: ['план', 'заплан', 'далее', 'следующ'],
      emptyState: 'Пока нет публично запланированных задач.',
    },
    {
      key: 'in_progress',
      label: 'В работе',
      shortLabel: 'В работе',
      description: 'То, что уже взяли в разработку и над чем команда работает прямо сейчас.',
      exactSlugs: ['in-progress', 'in_progress', 'progress', 'doing', 'wip', 'active-work'],
      slugKeywords: ['progress', 'doing', 'wip', 'active', 'work', 'develop'],
      nameKeywords: ['в работе', 'делаем', 'разработ', 'работаем', 'реализ'],
      emptyState: 'Сейчас нет задач в активной разработке.',
    },
    {
      key: 'released',
      label: 'Сделано / релизы',
      shortLabel: 'Готово',
      description: 'Что уже доставлено пользователям и можно обсуждать качество реализации.',
      exactSlugs: ['done', 'completed', 'shipped', 'released', 'changelog'],
      slugKeywords: ['done', 'complete', 'ship', 'release', 'changelog', 'live'],
      nameKeywords: ['сделан', 'готов', 'релиз', 'выпущ', 'готово'],
      emptyState: 'В этом столбце пока нет завершённых изменений.',
    },
  ]

  let categoryCounts: ComunCategoryCount[] = Array.isArray(data?.categoryCounts) ? data.categoryCounts : []
  let totalPostsCount: number | null =
    typeof data?.totalCount === 'number' ? Number(data.totalCount) : null
  let uncategorizedPostsCount: number =
    typeof data?.uncategorizedCount === 'number' ? Math.max(Number(data.uncategorizedCount), 0) : 0
  let lastCategoryCountsRef = data?.categoryCounts
  let lastTotalCountRef = data?.totalCount
  let lastUncategorizedCountRef = data?.uncategorizedCount
  let roadmapPreviewStates: Partial<Record<RoadmapStageKey, RoadmapPreviewState>> = {}
  let lastRoadmapPreviewSignature = ''
  let roadmapPreviewRequestSeq = 0
  let publicRoadmapModalOpen = false
  let publicRoadmapBodyOverflowBeforeOpen: string | null = null
  let publicRoadmapUrl = ''

  $: if (data?.posts && data.posts !== lastPostsRef) {
    lastPostsRef = data.posts
    posts = data.posts ?? []
    hasMore = posts.length === pageSize
    loadingMore = false
  }
  $: if (data?.comun && data.comun !== lastComunRef) {
    lastComunRef = data.comun
    comun = data.comun ?? null
  }
  $: if (Array.isArray(data?.categoryCounts) && data.categoryCounts !== lastCategoryCountsRef) {
    lastCategoryCountsRef = data.categoryCounts
    categoryCounts = data.categoryCounts
  }
  $: if (data && data.totalCount !== lastTotalCountRef) {
    lastTotalCountRef = data.totalCount
    totalPostsCount = typeof data.totalCount === 'number' ? Number(data.totalCount) : totalPostsCount
  }
  $: if (data && data.uncategorizedCount !== lastUncategorizedCountRef) {
    lastUncategorizedCountRef = data.uncategorizedCount
    uncategorizedPostsCount =
      typeof data.uncategorizedCount === 'number'
        ? Math.max(Number(data.uncategorizedCount), 0)
        : uncategorizedPostsCount
  }

  $: hiddenAuthorKeys = new Set(
    ($userSettings.hiddenAuthors ?? []).map((value) => value.toLowerCase())
  )
  const authorKey = (backendPost: { author?: { username?: string } }) =>
    (backendPost.author?.username ?? '').trim().toLowerCase()
  const isAuthorVisible = (backendPost: { author?: { username?: string } }) => {
    const key = authorKey(backendPost)
    if (!key) return true
    return !hiddenAuthorKeys.has(key)
  }
  $: visiblePosts = posts.filter(isAuthorVisible)

  const isModerator = () => Boolean(comun?.can_moderate && $siteToken)
  const canManageComunModerators = () => Boolean(comun?.can_manage_moderators && $siteToken)
  const isComunCreator = () =>
    Boolean($siteToken && $siteUser?.id && comun?.creator?.id && $siteUser.id === comun.creator.id)

  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Comuna'
  $: comunName = comun?.name || 'Комуна'
  $: welcomePostView = comun?.welcome_post ? backendPostToPostView(comun.welcome_post) : null
  $: comunTopMembers = comun?.activity?.top_members ?? []
  $: comunParticipantsCount = comun?.activity?.participants_count ?? comunTopMembers.length
  $: comunRating = comun?.rating ?? { score: 0, upvotes: 0, downvotes: 0, user_vote: 0 }
  $: comunRatingScore = Number(comunRating?.score ?? 0)
  $: comunRatingUpvotes = Number(comunRating?.upvotes ?? 0)
  $: comunRatingDownvotes = Number(comunRating?.downvotes ?? 0)
  $: comunUserVote = Number(comunRating?.user_vote ?? 0)
  $: comunBacklogCategory =
    (comun?.categories ?? []).find((category) => category.slug === COMUN_BACKLOG_CATEGORY_SLUG) ?? null
  $: myFeedComunSlugs = ($userSettings.myFeedComuns ?? []).map((slug) => slug.trim()).filter(Boolean)
  $: currentComunSlug = (comun?.slug ?? '').trim()
  $: isSubscribedToComun = !!currentComunSlug && myFeedComunSlugs.includes(currentComunSlug)
  $: title = `${comunName} — ${siteTitle}`
  $: description =
    comun?.product_description || `Посты и обсуждения продукта «${comunName}» на ${siteTitle}.`
  $: canonicalUrl = new URL(
    $page.url.pathname + (selectedCategorySlug ? `?category=${encodeURIComponent(selectedCategorySlug)}` : ''),
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()
  $: publicRoadmapUrl = comun?.slug ? `/comuns/${comun.slug}/roadmap` : ''
  $: if (browser) {
    if (publicRoadmapModalOpen) {
      if (publicRoadmapBodyOverflowBeforeOpen === null) {
        publicRoadmapBodyOverflowBeforeOpen = document.body.style.overflow
        document.body.style.overflow = 'hidden'
      }
    } else if (publicRoadmapBodyOverflowBeforeOpen !== null) {
      document.body.style.overflow = publicRoadmapBodyOverflowBeforeOpen
      publicRoadmapBodyOverflowBeforeOpen = null
    }
  }

  const cloneComun = (value: BackendComun | null): BackendComun | null =>
    value ? JSON.parse(JSON.stringify(value)) : null

  const hashString = (value?: string | null) => {
    const source = (value ?? '').trim() || 'comuna'
    let hash = 0
    for (let i = 0; i < source.length; i += 1) {
      hash = (hash * 31 + source.charCodeAt(i)) % 360
    }
    return Math.abs(hash)
  }

  const comunPlaceholderStyle = (name?: string | null) => `--comun-h:${hashString(name)}`

  const comunInitial = (name?: string | null) =>
    (name ?? '').trim().slice(0, 1).toUpperCase() || 'C'

  const openPublicRoadmapModal = () => {
    if (!comun?.slug) return
    publicRoadmapModalOpen = true
  }

  const closePublicRoadmapModal = () => {
    publicRoadmapModalOpen = false
  }

  const onPublicRoadmapLinkClick = (event: MouseEvent) => {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return
    }
    event.preventDefault()
    openPublicRoadmapModal()
  }

  const onWindowKeydown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && publicRoadmapModalOpen) {
      closePublicRoadmapModal()
    }
  }

  const normalizeIds = (values: Array<number | null | undefined>) =>
    Array.from(new Set(values.filter((value): value is number => Number.isFinite(value as number) && Number(value) > 0).map(Number))).sort((a, b) => a - b)

  const comunModeratorIds = (value: BackendComun | null) =>
    normalizeIds(
      ((value?.moderator_ids as number[] | undefined) ??
        (value?.moderators ?? []).map((moderator) => moderator.id ?? 0)) as number[]
    )

  const comunCategoryIds = (value: BackendComun | null) =>
    normalizeIds(
      ((value?.category_ids as number[] | undefined) ??
        (value?.categories ?? []).map((category) => category.id ?? 0)) as number[]
    )

  const settingsComparable = (value: BackendComun | null) =>
    JSON.stringify({
      website_url: (value?.website_url ?? '').trim(),
      logo_url: (value?.logo_url ?? '').trim(),
      product_description: (value?.product_description ?? '').trim(),
      target_audience: (value?.target_audience ?? '').trim(),
      hide_from_home: Boolean(value?.hide_from_home),
      hide_from_fresh: Boolean(value?.hide_from_fresh),
      product_tag_id: value?.product_tag_id ?? value?.product_tag?.id ?? null,
      category_ids: comunCategoryIds(value),
      moderator_ids: comunModeratorIds(value),
      welcome_post_ref: String(value?.welcome_post_ref ?? value?.welcome_post_id ?? '').trim(),
    })

  const userInitials = (username?: string | null) =>
    (username || '?').trim().slice(0, 1).toUpperCase() || '?'

  const userDisplayName = (user?: { username?: string | null; display_name?: string | null } | null) => {
    const displayName = (user?.display_name ?? '').trim()
    if (displayName) return displayName
    const username = (user?.username ?? '').trim()
    return username ? `@${username}` : 'Пользователь'
  }

  const isSuggestionsComunCategory = (category?: BackendComunCategory | null) =>
    Boolean(category?.slug && COMUN_SUGGESTIONS_CATEGORY_SLUGS.has(category.slug))

  const canMovePostToBacklog = (post: BackendPost) =>
    Boolean(
      isModerator() &&
        comunBacklogCategory?.id &&
        isSuggestionsComunCategory(post.comun_category) &&
        post.comun_category_id !== comunBacklogCategory.id
    )

  const normalizeRoadmapToken = (value?: string | null) =>
    (value ?? '')
      .toLowerCase()
      .replace(/[_\s]+/g, '-')
      .replace(/-+/g, '-')
      .trim()

  const normalizeRoadmapText = (value?: string | null) =>
    (value ?? '')
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim()

  const scoreRoadmapCategoryCandidate = (
    stage: RoadmapStageDefinition,
    category: BackendComunCategory
  ): number => {
    const slug = normalizeRoadmapToken(category.slug)
    const name = normalizeRoadmapText(category.name)
    if (!slug && !name) return 0
    if (stage.exactSlugs.includes(slug)) return 100
    if (stage.key === 'suggestions' && COMUN_SUGGESTIONS_CATEGORY_SLUGS.has(slug)) return 95
    let score = 0
    if (stage.slugKeywords.some((keyword) => slug.includes(keyword))) score = Math.max(score, 70)
    if (stage.nameKeywords.some((keyword) => name.includes(keyword))) score = Math.max(score, 60)
    return score
  }

  const buildRoadmapStages = (
    categories: BackendComunCategory[],
    countById: Map<number, number>
  ): RoadmapStage[] => {
    const usedCategoryIds = new Set<number>()
    const nextStages: RoadmapStage[] = []
    for (const stage of ROADMAP_STAGE_DEFINITIONS) {
      const candidates = categories
        .filter((category) => !usedCategoryIds.has(category.id))
        .map((category) => ({
          category,
          score: scoreRoadmapCategoryCandidate(stage, category),
        }))
        .filter((entry) => entry.score > 0)
        .sort((a, b) => {
          if (b.score !== a.score) return b.score - a.score
          const countDiff = (countById.get(b.category.id) ?? 0) - (countById.get(a.category.id) ?? 0)
          if (countDiff !== 0) return countDiff
          const sortDiff = Number(a.category.sort_order ?? 0) - Number(b.category.sort_order ?? 0)
          if (sortDiff !== 0) return sortDiff
          return a.category.name.localeCompare(b.category.name, 'ru')
        })
      const best = candidates[0]
      if (!best) continue
      usedCategoryIds.add(best.category.id)
      nextStages.push({
        ...stage,
        category: best.category,
        count: Math.max(0, Number(countById.get(best.category.id) ?? 0)),
      })
    }
    return nextStages
  }

  const roadmapStageStyleVars = (stageKey: RoadmapStageKey) => {
    switch (stageKey) {
      case 'suggestions':
        return '--roadmap-stage-h: 201; --roadmap-stage-s: 88%; --roadmap-stage-l: 47%;'
      case 'backlog':
        return '--roadmap-stage-h: 262; --roadmap-stage-s: 72%; --roadmap-stage-l: 52%;'
      case 'planned':
        return '--roadmap-stage-h: 34; --roadmap-stage-s: 88%; --roadmap-stage-l: 50%;'
      case 'in_progress':
        return '--roadmap-stage-h: 153; --roadmap-stage-s: 77%; --roadmap-stage-l: 40%;'
      case 'released':
        return '--roadmap-stage-h: 340; --roadmap-stage-s: 78%; --roadmap-stage-l: 52%;'
      default:
        return '--roadmap-stage-h: 220; --roadmap-stage-s: 70%; --roadmap-stage-l: 50%;'
    }
  }

  const roadmapStagePillLabel = (stageKey: RoadmapStageKey) => {
    switch (stageKey) {
      case 'suggestions':
        return 'Собираем идеи'
      case 'backlog':
        return 'Приоритизируем'
      case 'planned':
        return 'Планируем'
      case 'in_progress':
        return 'Делаем'
      case 'released':
        return 'Доставили'
      default:
        return 'Этап'
    }
  }

  const stripRoadmapHtml = (value?: string | null) =>
    (value ?? '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&nbsp;/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()

  const looksLikeSerializedRoadmapContent = (value?: string | null) => {
    const trimmed = (value ?? '').trim()
    if (!trimmed) return false
    if (trimmed.startsWith('{') && trimmed.includes('"blocks"')) return true
    return /^eyJ[0-9A-Za-z+/=]{20,}$/.test(trimmed)
  }

  const collectRoadmapBlockText = (block: any) => {
    const data = block?.data ?? {}
    const chunks: string[] = []
    const pushChunk = (value: unknown) => {
      if (typeof value !== 'string') return
      const normalized = stripRoadmapHtml(value)
      if (normalized) chunks.push(normalized)
    }

    pushChunk(data.text)
    pushChunk(data.caption)
    pushChunk(data.title)
    pushChunk(data.code)
    pushChunk(data.alt)

    if (Array.isArray(data.items)) {
      for (const item of data.items) {
        if (typeof item === 'string') {
          pushChunk(item)
          continue
        }
        if (item && typeof item === 'object') {
          pushChunk((item as { text?: string }).text)
        }
      }
    }

    if (Array.isArray(data.content)) {
      for (const row of data.content) {
        if (!Array.isArray(row)) continue
        for (const cell of row) {
          pushChunk(typeof cell === 'string' ? cell : '')
        }
      }
    }

    return chunks
  }

  const extractRoadmapTextFromSerializedContent = (value?: string | null) => {
    if (!looksLikeSerializedRoadmapContent(value)) return ''
    const parsed = deserializeEditorModel((value ?? '').trim())
    const blocks = Array.isArray(parsed?.blocks) ? parsed.blocks : []
    const chunks: string[] = []
    for (const block of blocks) {
      chunks.push(...collectRoadmapBlockText(block))
    }
    return chunks.join(' ').trim()
  }

  const roadmapSnippet = (post: BackendPost, maxLength = 150) => {
    const serializedText = extractRoadmapTextFromSerializedContent(post.content)
    const text = serializedText || stripRoadmapHtml(post.content)
    if (!serializedText && looksLikeSerializedRoadmapContent(post.content)) return ''
    if (!text) return ''
    if (text.length <= maxLength) return text
    return `${text.slice(0, maxLength - 1).trimEnd()}…`
  }

  const roadmapPreviewScore = (post: BackendPost) =>
    Number(post.likes_count ?? 0) * 3 +
    Number(post.comments_count ?? 0) * 4 +
    Number(post.views_count ?? 0) * 0.02

  const sortRoadmapPreviewPosts = (items: BackendPost[]) =>
    [...items]
      .sort((a, b) => {
        const scoreDiff = roadmapPreviewScore(b) - roadmapPreviewScore(a)
        if (scoreDiff !== 0) return scoreDiff
        return String(b.created_at ?? '').localeCompare(String(a.created_at ?? ''))
      })
      .slice(0, ROADMAP_PREVIEW_LIMIT)

  const formatRoadmapDate = (value?: string | null) => {
    if (!value) return ''
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return ''
    return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'short' }).format(parsed)
  }

  const formatRoadmapCount = (value?: number | null) => {
    const normalized = Math.max(0, Number(value ?? 0) || 0)
    return new Intl.NumberFormat('ru-RU').format(normalized)
  }

  const getRoadmapPreviewState = (stageKey: RoadmapStageKey): RoadmapPreviewState =>
    roadmapPreviewStates[stageKey] ?? { loading: false, error: null, posts: [] }

  const openRoadmapSubmitFlow = () => {
    if (!comun?.slug) return
    const suggestionsCategory =
      roadmapStages.find((stage) => stage.key === 'suggestions')?.category ??
      (comun?.categories ?? []).find((category) => isSuggestionsComunCategory(category))
    const target = suggestionsCategory?.slug
      ? `/comuns/${comun.slug}/new-post?category=${encodeURIComponent(suggestionsCategory.slug)}`
      : `/comuns/${comun.slug}/new-post`
    if (isModerator()) {
      goto(target)
      return
    }
    if (!$siteToken) {
      const next = encodeURIComponent(target)
      goto(`/account?next=${next}`)
      return
    }
    goto(target)
  }

  const loadRoadmapPreviews = async () => {
    const slug = (comun?.slug ?? '').trim()
    const stagesSnapshot = roadmapStages
    if (!slug || !stagesSnapshot.length) {
      roadmapPreviewStates = {}
      return
    }

    const requestId = ++roadmapPreviewRequestSeq
    const nextStates: Partial<Record<RoadmapStageKey, RoadmapPreviewState>> = {}
    for (const stage of stagesSnapshot) {
      nextStates[stage.key] = { loading: true, error: null, posts: [] }
    }
    roadmapPreviewStates = nextStates

    try {
      const headers = $siteToken ? { Authorization: `Bearer ${$siteToken}` } : undefined
      const results = await Promise.all(
        stagesSnapshot.map(async (stage) => {
          const url = new URL(buildComunPostsUrl(slug, { categorySlug: stage.category.slug }))
          url.searchParams.set('limit', String(ROADMAP_PREVIEW_FETCH_LIMIT))
          url.searchParams.set('offset', '0')
          const response = await fetch(url.toString(), headers ? { headers } : undefined)
          const payload = await response.json().catch(() => ({}))
          if (!response.ok) {
            throw new Error(
              typeof payload?.error === 'string' && payload.error
                ? payload.error
                : 'Не удалось загрузить превью'
            )
          }
          return {
            stageKey: stage.key,
            posts: sortRoadmapPreviewPosts((payload?.posts ?? []) as BackendPost[]),
          }
        })
      )
      if (requestId !== roadmapPreviewRequestSeq) return
      const completedStates: Partial<Record<RoadmapStageKey, RoadmapPreviewState>> = {}
      for (const stage of stagesSnapshot) {
        completedStates[stage.key] = { loading: false, error: null, posts: [] }
      }
      for (const result of results) {
        completedStates[result.stageKey] = {
          loading: false,
          error: null,
          posts: result.posts,
        }
      }
      roadmapPreviewStates = completedStates
    } catch (error) {
      if (requestId !== roadmapPreviewRequestSeq) return
      const failedStates: Partial<Record<RoadmapStageKey, RoadmapPreviewState>> = {}
      for (const stage of stagesSnapshot) {
        failedStates[stage.key] = {
          loading: false,
          error: error instanceof Error ? error.message : 'Ошибка загрузки',
          posts: [],
        }
      }
      roadmapPreviewStates = failedStates
    }
  }

  $: categoryCountById = new Map<number, number>(
    (categoryCounts ?? [])
      .map((row) => [Number(row?.category_id ?? 0), Math.max(0, Number(row?.count ?? 0) || 0)] as const)
      .filter(([categoryId]) => categoryId > 0)
  )
  $: roadmapStages = buildRoadmapStages(comun?.categories ?? [], categoryCountById)
  $: roadmapStageSlugSet = new Set(roadmapStages.map((stage) => stage.category.slug))
  $: roadmapHasBacklog = roadmapStages.some((stage) => stage.key === 'backlog')
  $: roadmapCanOpenModal = roadmapHasBacklog || roadmapStages.length >= 2
  $: roadmapModalVisible = publicRoadmapModalOpen && roadmapCanOpenModal
  $: roadmapTrackedCount = roadmapStages.reduce((sum, stage) => sum + Math.max(stage.count, 0), 0)
  $: roadmapReleasedCount =
    roadmapStages.find((stage) => stage.key === 'released')?.count ?? 0
  $: roadmapSelectedStage =
    roadmapStages.find((stage) => stage.category.slug === selectedCategorySlug) ?? null
  $: roadmapSignature =
    (comun?.slug ?? '').trim() && roadmapStages.length
      ? `${comun?.slug}:${roadmapStages.map((stage) => `${stage.key}:${stage.category.slug}`).join('|')}`
      : ''

  const toggleComunInMyFeed = async () => {
    const slug = (comun?.slug ?? '').trim()
    if (!slug) return
    if (!$siteToken) {
      const next = encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)
      goto(`/account?next=${next}`)
      return
    }
    const next = new Set<string>(myFeedComunSlugs)
    if (next.has(slug)) {
      next.delete(slug)
      $userSettings = {
        ...$userSettings,
        myFeedComuns: Array.from(next),
      }
      toast({ content: 'Комуна убрана из "Моей ленты"' })
      return
    }
    next.add(slug)
    $userSettings = {
      ...$userSettings,
      myFeedComuns: Array.from(next),
    }
    toast({ content: 'Посты этой комуны будут попадать в "Мою ленту"' })
  }

  const voteComun = async (value: 1 | -1) => {
    const slug = (comun?.slug ?? '').trim()
    if (!slug || comunVoteSaving) return
    if (!$siteToken) {
      const next = encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)
      goto(`/account?next=${next}`)
      return
    }
    comunVoteSaving = true
    try {
      const response = await fetch(buildComunVoteUrl(slug), {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ value }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось сохранить голос')
      }
      if (payload?.rating && comun) {
        comun = {
          ...comun,
          rating: payload.rating,
        }
      }
      const appliedVote = Number(payload?.rating?.user_vote ?? 0)
      if (appliedVote === 1) {
        toast({
          content: 'Разместите свой текущий или потенциальный кейс использования - это поможет команде',
          type: 'success',
        })
      } else if (appliedVote === -1) {
        toast({
          content:
            'Разместите пост с описанием, чем продукт не нравится и как сделать лучше - это очень поможет команде',
          type: 'warning',
        })
      } else {
        toast({ content: 'Голос по комуне снят' })
      }
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Ошибка голосования', type: 'error' })
    } finally {
      comunVoteSaving = false
    }
  }

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  const buildPostsUrl = (offset: number) => {
    if (!comun?.slug) return ''
    const url = new URL(buildComunPostsUrl(comun.slug, { categorySlug: selectedCategorySlug || undefined }))
    url.searchParams.set('limit', String(pageSize))
    url.searchParams.set('offset', String(offset))
    return url.toString()
  }

  const applyPostsPayload = (payload: any, reset = false) => {
    if (payload?.comun) {
      comun = payload.comun
    }
    if (Array.isArray(payload?.category_counts)) {
      categoryCounts = payload.category_counts
    }
    if (typeof payload?.total_count === 'number') {
      totalPostsCount = Math.max(Number(payload.total_count), 0)
    }
    if (typeof payload?.uncategorized_count === 'number') {
      uncategorizedPostsCount = Math.max(Number(payload.uncategorized_count), 0)
    }
    const nextPosts = (payload?.posts ?? []) as BackendPost[]
    if (reset) {
      posts = nextPosts
    } else if (nextPosts.length) {
      posts = [...posts, ...nextPosts]
    }
    hasMore = nextPosts.length === pageSize
  }

  const loadPosts = async (reset = false) => {
    if (loadingMore || loadingCategory) return
    const url = buildPostsUrl(reset ? 0 : posts.length)
    if (!url) return
    if (reset) {
      loadingCategory = true
    } else {
      loadingMore = true
    }
    try {
      const response = await fetch(url, $siteToken ? { headers: { Authorization: `Bearer ${$siteToken}` } } : undefined)
      if (!response.ok) {
        throw new Error('Не удалось загрузить посты комуны')
      }
      const payload = await response.json()
      applyPostsPayload(payload, reset)
    } catch (error) {
      console.error(error)
      toast({ content: error instanceof Error ? error.message : 'Ошибка загрузки', type: 'error' })
    } finally {
      loadingMore = false
      loadingCategory = false
    }
  }

  const maybeLoadMore = () => {
    if (!browser || loadingMore || loadingCategory || !hasMore) return
    const viewportBottom = window.scrollY + window.innerHeight
    const pageHeight = document.documentElement.scrollHeight
    if (pageHeight - viewportBottom <= scrollThreshold) {
      void loadPosts(false)
    }
  }

  const onScroll = () => {
    if (scrollRaf !== null) return
    scrollRaf = window.requestAnimationFrame(() => {
      scrollRaf = null
      maybeLoadMore()
    })
  }

  const setCategoryFilter = async (slug: string) => {
    if (slug === selectedCategorySlug) return
    selectedCategorySlug = slug
    hasMore = true
    await goto(
      slug ? `${$page.url.pathname}?category=${encodeURIComponent(slug)}` : $page.url.pathname,
      { replaceState: true, noScroll: true, keepFocus: true }
    )
    await loadPosts(true)
    if (browser) window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const refreshComunManage = async () => {
    if (!comun?.slug || !$siteToken) return
    settingsLoading = true
    settingsError = ''
    try {
      const response = await fetch(buildComunUrl(comun.slug), {
        headers: { Authorization: `Bearer ${$siteToken}` },
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось загрузить настройки комуны')
      }
      if (payload?.comun) {
        comun = payload.comun
        settingsDraft = cloneComun(payload.comun)
        settingsCategoryOptions = payload.comun?.options?.categories ?? []
        settingsTagOptions = payload.comun?.options?.tags ?? []
        settingsUserOptions = payload.comun?.options?.users ?? []
      }
    } catch (error) {
      settingsError = error instanceof Error ? error.message : 'Ошибка загрузки'
    } finally {
      settingsLoading = false
    }
  }

  const openSettings = async () => {
    if (!$siteToken) {
      const next = `${$page.url.pathname}?settings=1`
      goto(`/account?next=${encodeURIComponent(next)}`)
      return
    }
    settingsTagSearch = ''
    settingsUserSearch = ''
    settingsDraft = cloneComun(comun)
    await refreshComunManage()
    if (!comun?.can_moderate) {
      toast({ content: 'Настройки доступны только модераторам комуны', type: 'warning' })
      return
    }
    settingsOpen = true
  }

  const toggleDraftCategory = (categoryId: number) => {
    if (!settingsDraft) return
    const current = new Set((settingsDraft.category_ids ?? settingsDraft.categories ?? []).map((item: any) =>
      typeof item === 'number' ? item : item?.id
    ).filter(Boolean))
    if (current.has(categoryId)) current.delete(categoryId)
    else current.add(categoryId)
    settingsDraft = { ...settingsDraft, category_ids: Array.from(current) as number[] }
  }

  const setDraftModeratorIds = (ids: number[]) => {
    if (!settingsDraft) return
    const creatorId = Number(settingsDraft.creator?.id ?? comun?.creator?.id ?? 0)
    const normalizedIds = normalizeIds([...ids, creatorId > 0 ? creatorId : 0])
    const byId = new Map<number, ComunUserOption>()
    for (const user of settingsUserOptions) byId.set(user.id, user)
    for (const moderator of settingsDraft.moderators ?? []) {
      byId.set(moderator.id, {
        id: moderator.id,
        username: moderator.username,
        display_name: moderator.display_name ?? null,
      })
    }
    settingsDraft = {
      ...settingsDraft,
      moderator_ids: normalizedIds,
      moderators: normalizedIds.map((id) => {
        const user = byId.get(id)
        return {
          id,
          username: user?.username ?? String(id),
          display_name: user?.display_name ?? null,
        }
      }),
    }
  }

  const addDraftModerator = (userId: number) => {
    if (!settingsDraft || !canManageComunModerators()) return
    setDraftModeratorIds([...comunModeratorIds(settingsDraft), userId])
  }

  const removeDraftModerator = (userId: number) => {
    if (!settingsDraft || !canManageComunModerators()) return
    setDraftModeratorIds(comunModeratorIds(settingsDraft).filter((id) => id !== userId))
  }

  const chooseDraftTag = (tag: ComunTagOption) => {
    if (!settingsDraft) return
    settingsDraft = {
      ...settingsDraft,
      product_tag_id: tag.id,
      product_tag: { id: tag.id, name: tag.name, lemma: tag.lemma ?? null },
    }
  }

  const clearDraftTag = () => {
    if (!settingsDraft) return
    settingsDraft = { ...settingsDraft, product_tag_id: null, product_tag: null }
  }

  const normalizeTagInput = (value: string) =>
    value.trim().replace(/^#+/, '').replace(/\s+/g, ' ').trim()

  $: normalizedTagSearch = settingsTagSearch.trim().toLowerCase()
  $: normalizedTagCreateValue = normalizeTagInput(settingsTagSearch)
  $: hasExactTagMatch = (settingsTagOptions ?? []).some((tag) => {
    const needle = normalizedTagCreateValue.toLowerCase()
    if (!needle) return false
    return [tag.name, tag.lemma ?? '']
      .map((value) => normalizeTagInput(value).toLowerCase())
      .some((value) => value === needle)
  })
  $: draftCategoryIdSet = new Set<number>(
    ((settingsDraft?.category_ids as number[] | undefined) ??
      (settingsDraft?.categories ?? []).map((item) => item.id)) as number[]
  )
  $: filteredTagOptions = (settingsTagOptions ?? []).filter((tag) => {
    if (!normalizedTagSearch) return true
    return [tag.name, tag.lemma ?? ''].some((value) => value.toLowerCase().includes(normalizedTagSearch))
  }).slice(0, 30)
  $: normalizedUserSearch = settingsUserSearch.trim().toLowerCase()
  $: draftModeratorIdSet = new Set<number>(comunModeratorIds(settingsDraft))
  $: settingsHasChanges = settingsComparable(settingsDraft) !== settingsComparable(comun)
  $: settingsCanDismiss =
    !settingsHasChanges && !settingsSaving && !settingsLogoUploading && !settingsTagCreating
  $: filteredUserOptions = (settingsUserOptions ?? [])
    .filter((user) => {
      if (!normalizedUserSearch) return true
      return [user.username, user.display_name ?? '']
        .some((value) => value.toLowerCase().includes(normalizedUserSearch))
    })
    .slice(0, 50)
  $: selectedModeratorUsers = comunModeratorIds(settingsDraft).map((id) => {
    const fromOptions = settingsUserOptions.find((user) => user.id === id)
    if (fromOptions) return fromOptions
    const fromDraft = settingsDraft?.moderators?.find((moderator) => moderator.id === id)
    return {
      id,
      username: fromDraft?.username ?? String(id),
      display_name: fromDraft?.display_name ?? null,
    }
  })

  const createTagAndChooseDraft = async () => {
    const tagName = normalizeTagInput(settingsTagSearch)
    if (!tagName || settingsTagCreating) return
    settingsTagCreating = true
    try {
      const response = await fetch(buildTagsEnsureUrl(), {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ name: tagName }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || !payload?.tag?.id) {
        throw new Error(payload?.error || 'Не удалось добавить тег')
      }
      const nextTag: ComunTagOption = {
        id: Number(payload.tag.id),
        name: String(payload.tag.name ?? tagName),
        lemma: payload.tag.lemma ? String(payload.tag.lemma) : null,
      }
      const nextOptions = [...(settingsTagOptions ?? [])]
      const existingIndex = nextOptions.findIndex((tag) => tag.id === nextTag.id)
      if (existingIndex >= 0) {
        nextOptions[existingIndex] = nextTag
      } else {
        nextOptions.push(nextTag)
      }
      settingsTagOptions = nextOptions.sort((a, b) => a.name.localeCompare(b.name, 'ru'))
      chooseDraftTag(nextTag)
      settingsTagSearch = nextTag.name
      toast({
        content: payload.created ? 'Тег добавлен и выбран' : 'Тег найден и выбран',
        type: 'success',
      })
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Не удалось добавить тег', type: 'error' })
    } finally {
      settingsTagCreating = false
    }
  }

  const saveSettings = async () => {
    if (!comun?.slug || !settingsDraft) return
    settingsSaving = true
    settingsError = ''
    try {
      const response = await fetch(buildComunUrl(comun.slug), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({
          website_url: settingsDraft.website_url ?? '',
          logo_url: settingsDraft.logo_url ?? '',
          product_description: settingsDraft.product_description ?? '',
          target_audience: settingsDraft.target_audience ?? '',
          hide_from_home: canManageComunModerators() ? Boolean(settingsDraft.hide_from_home) : undefined,
          hide_from_fresh: canManageComunModerators() ? Boolean(settingsDraft.hide_from_fresh) : undefined,
          moderator_ids: canManageComunModerators() ? comunModeratorIds(settingsDraft) : undefined,
          product_tag_id: settingsDraft.product_tag_id ?? null,
          category_ids: settingsDraft.category_ids ?? (settingsDraft.categories ?? []).map((category) => category.id),
          welcome_post_ref: settingsDraft.welcome_post_ref ?? '',
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось сохранить настройки')
      }
      comun = payload.comun ?? comun
      settingsDraft = cloneComun(comun)
      settingsOpen = false
      toast({ content: 'Настройки комуны сохранены', type: 'success' })
      await loadPosts(true)
    } catch (error) {
      settingsError = error instanceof Error ? error.message : 'Ошибка сохранения'
    } finally {
      settingsSaving = false
    }
  }

  const pickSettingsLogo = () => {
    if (!isModerator()) return
    settingsLogoInput?.click()
  }

  const onSettingsLogoSelected = async (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    const file = input?.files?.[0]
    if (!file || !settingsDraft) return

    settingsLogoUploading = true
    try {
      const uploadedUrl = await uploadSiteImage(file)
      settingsDraft = { ...settingsDraft, logo_url: uploadedUrl }
      toast({ content: 'Логотип загружен. Нажмите «Сохранить» для применения.', type: 'success' })
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Не удалось загрузить логотип', type: 'error' })
    } finally {
      settingsLogoUploading = false
      if (input) input.value = ''
    }
  }

  const setWelcomePost = async (postId: number) => {
    if (!comun?.slug || !isModerator()) return
    try {
      const response = await fetch(buildComunUrl(comun.slug), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ welcome_post_id: postId }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload?.error || 'Не удалось выбрать приветственный пост')
      comun = payload.comun ?? comun
      toast({ content: 'Приветственный пост обновлен', type: 'success' })
      await loadPosts(true)
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Ошибка обновления', type: 'error' })
    }
  }

  const updatePostCategory = async (postId: number, categoryId: number | null) => {
    if (!comun?.slug || !isModerator()) return false
    const previousPost = posts.find((post) => post.id === postId) ?? null
    const previousCategoryId =
      previousPost && Number(previousPost.comun_category_id ?? 0) > 0
        ? Number(previousPost.comun_category_id)
        : null
    categorySavingPostIds = new Set([...categorySavingPostIds, postId])
    try {
      const response = await fetch(buildComunPostCategoryUrl(comun.slug, postId), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ category_id: categoryId }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось обновить категорию')
      }
      const assignment = payload?.assignment
      const nextCategoryId =
        assignment && Number(assignment?.category_id ?? 0) > 0 ? Number(assignment.category_id) : null
      posts = posts.map((post) => {
        if (post.id !== postId) return post
        return {
          ...post,
          comun_category_id: nextCategoryId,
          comun_category: assignment?.category ?? null,
        }
      })
      if (previousCategoryId !== nextCategoryId && (categoryCounts ?? []).length) {
        categoryCounts = (categoryCounts ?? []).map((row) => {
          const rowCategoryId = Number(row?.category_id ?? 0)
          let nextCount = Math.max(0, Number(row?.count ?? 0) || 0)
          if (previousCategoryId && rowCategoryId === previousCategoryId) {
            nextCount = Math.max(nextCount - 1, 0)
          }
          if (nextCategoryId && rowCategoryId === nextCategoryId) {
            nextCount += 1
          }
          return { ...row, count: nextCount }
        })
        if (!previousCategoryId && nextCategoryId) {
          uncategorizedPostsCount = Math.max(uncategorizedPostsCount - 1, 0)
        } else if (previousCategoryId && !nextCategoryId) {
          uncategorizedPostsCount += 1
        }
      }
      if (roadmapCanOpenModal) {
        void loadRoadmapPreviews()
      }
      return true
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Ошибка обновления категории', type: 'error' })
      return false
    } finally {
      const next = new Set(categorySavingPostIds)
      next.delete(postId)
      categorySavingPostIds = next
    }
  }

  const onPostCategoryChange = (event: Event, postId: number) => {
    const target = event.currentTarget as HTMLSelectElement | null
    if (!target) return
    const value = target.value ? Number(target.value) : null
    void updatePostCategory(postId, value)
  }

  const movePostToBacklog = async (postId: number) => {
    if (!comunBacklogCategory?.id) return
    const updated = await updatePostCategory(postId, comunBacklogCategory.id)
    if (updated) {
      toast({ content: 'Пост добавлен в Беклог', type: 'success' })
    }
  }

  $: wantsSettingsOpenFromUrl = $page.url.searchParams.get('settings') === '1'

  $: if (browser && comun?.slug && $siteToken && $siteToken !== lastAuthRefreshToken) {
    lastAuthRefreshToken = $siteToken
    void refreshComunManage()
  }

  $: if (!$siteToken) {
    lastAuthRefreshToken = null
    autoSettingsOpenHandled = false
  }

  $: if (!wantsSettingsOpenFromUrl) {
    autoSettingsOpenHandled = false
  }

  $: if (!roadmapSignature) {
    lastRoadmapPreviewSignature = ''
    roadmapPreviewStates = {}
  }

  $: if (
    browser &&
    roadmapSignature &&
    roadmapSignature !== lastRoadmapPreviewSignature &&
    roadmapCanOpenModal
  ) {
    lastRoadmapPreviewSignature = roadmapSignature
    void loadRoadmapPreviews()
  }

  $: if (
    browser &&
    wantsSettingsOpenFromUrl &&
    $siteToken &&
    !settingsOpen &&
    !autoSettingsOpenHandled &&
    !settingsLoading
  ) {
    autoSettingsOpenHandled = true
    void openSettings()
  }

  onMount(() => {
    if (!browser) return
    if ($siteToken && !$siteUser) {
      void refreshSiteUser().catch(() => null)
    }
    maybeLoadMore()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('keydown', onWindowKeydown)
  })

  onDestroy(() => {
    if (browser) {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('keydown', onWindowKeydown)
      if (scrollRaf !== null) {
        window.cancelAnimationFrame(scrollRaf)
        scrollRaf = null
      }
      if (publicRoadmapBodyOverflowBeforeOpen !== null) {
        document.body.style.overflow = publicRoadmapBodyOverflowBeforeOpen
        publicRoadmapBodyOverflowBeforeOpen = null
      }
    }
  })
</script>

<div class="flex flex-col gap-6 max-w-4xl">
  <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 overflow-hidden">
    <div class="p-5 sm:p-6 flex flex-col gap-4">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div class="flex items-start gap-4 min-w-0">
          <div class="h-16 w-16 rounded-2xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
            {#if comun?.logo_url}
              <img src={comun.logo_url} alt={comun?.name ?? 'Логотип'} class="h-full w-full object-cover" />
            {:else}
              <div
                class="comun-logo-fallback h-full w-full grid place-items-center text-2xl font-bold"
                style={comunPlaceholderStyle(comun?.name)}
              >
                {comunInitial(comun?.name)}
              </div>
            {/if}
          </div>
          <div class="min-w-0">
            <Header noMargin>{comun?.name ?? 'Комуна'}</Header>
            {#if comun?.product_tag}
              <div
                class="mt-1 text-sm text-slate-600 dark:text-zinc-400"
                title="Записи опубликованные с данным тегом на всем сайте будут отображаться в этой комуне"
              >
                Тег продукта: <span class="font-medium">#{comun.product_tag.name}</span>
              </div>
            {:else}
              <div class="mt-1 text-sm text-amber-700 dark:text-amber-300">
                Тег продукта пока не выбран. Посты в ленте не появятся, пока модератор не задаст тег.
              </div>
            {/if}
            {#if comun?.creator?.username}
              <div class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
                Создатель:
                {#if comun?.creator?.id}
                  <a
                    href={`/id${comun.creator.id}`}
                    class="ml-1 text-slate-700 dark:text-zinc-300 hover:underline"
                    title={comun.creator.username ? `Профиль @${comun.creator.username}` : 'Профиль пользователя'}
                  >
                    {userDisplayName(comun.creator)}
                  </a>
                {:else}
                  <span class="ml-1 text-slate-700 dark:text-zinc-300">{userDisplayName(comun.creator)}</span>
                {/if}
              </div>
            {/if}
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <div class="inline-flex items-center gap-2 rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-50/80 dark:bg-zinc-800/50 px-2 py-2">
            <div class="px-2 text-xs">
              <div class="uppercase tracking-wide text-[10px] text-slate-500 dark:text-zinc-400">
                Рейтинг
              </div>
              <div class="font-semibold text-slate-900 dark:text-zinc-100">
                {comunRatingScore > 0 ? '+' : ''}{comunRatingScore}
              </div>
            </div>
            <button
              type="button"
              class="rounded-lg border px-2 py-1 text-xs transition-colors disabled:opacity-60 disabled:cursor-not-allowed {comunUserVote === 1
                ? 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300'
                : 'border-slate-200 dark:border-zinc-700 hover:bg-white dark:hover:bg-zinc-900/80'}"
              on:click={() => voteComun(1)}
              disabled={comunVoteSaving}
              title="Буду использовать"
            >
              Буду использовать · {comunRatingUpvotes}
            </button>
            <button
              type="button"
              class="rounded-lg border px-2 py-1 text-xs transition-colors disabled:opacity-60 disabled:cursor-not-allowed {comunUserVote === -1
                ? 'border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-300'
                : 'border-slate-200 dark:border-zinc-700 hover:bg-white dark:hover:bg-zinc-900/80'}"
              on:click={() => voteComun(-1)}
              disabled={comunVoteSaving}
              title="Не нравится"
            >
              Не нравится · {comunRatingDownvotes}
            </button>
          </div>
          <Button
            color={isSubscribedToComun ? 'ghost' : undefined}
            on:click={toggleComunInMyFeed}
            title={isSubscribedToComun ? 'Убрать коммуну из Моей ленты' : 'Добавить коммуну в Мою ленту'}
          >
            {isSubscribedToComun ? 'В моей ленте' : 'В мою ленту'}
          </Button>
          {#if publicRoadmapUrl && roadmapCanOpenModal}
            <a
              href={publicRoadmapUrl}
              on:click={onPublicRoadmapLinkClick}
              class="inline-flex items-center rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-zinc-800/60"
              title="Открыть публичную дорожную карту во всплывающем окне"
            >
              Публичный roadmap
            </a>
          {/if}
          {#if comun?.website_url}
            <a
              href={comun.website_url}
              target="_blank"
              rel="nofollow noopener"
              class="inline-flex items-center rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-zinc-800/60"
            >
              Сайт
            </a>
          {/if}
          {#if isComunCreator() && comun?.slug}
            <Button color="ghost" on:click={() => goto(`/comuns/${comun.slug}/settings`)}>
              Настройки комуны
            </Button>
          {/if}
        </div>
      </div>

      {#if comun?.product_description}
        <div class="text-sm leading-relaxed text-slate-700 dark:text-zinc-300 whitespace-pre-line">
          {comun.product_description}
        </div>
      {/if}

      {#if comun?.target_audience}
        <div class="text-sm text-slate-600 dark:text-zinc-400">
          <span class="font-medium text-slate-800 dark:text-zinc-200">Целевая аудитория:</span>
          {comun.target_audience}
        </div>
      {/if}

      {#if comunTopMembers.length}
        <div class="flex flex-col gap-2 pt-1">
          <div class="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
            <span class="uppercase tracking-wide">Рейтинг активности</span>
            <span>•</span>
            <span>{comunParticipantsCount} участников</span>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            {#each comunTopMembers as member}
              <a
                href={`/id${member.user_id}`}
                class="inline-flex items-center justify-center h-9 w-9 rounded-full overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 text-xs font-semibold text-slate-700 dark:text-zinc-200 hover:ring-2 hover:ring-blue-300/70 dark:hover:ring-blue-700/70 focus:outline-none focus:ring-2 focus:ring-blue-400/80 dark:focus:ring-blue-600/80 transition-shadow"
                title={`#${member.rank} @${member.username} — ${member.points} баллов`}
                aria-label={`#${member.rank} ${member.username}, ${member.points} баллов`}
              >
                {#if member.avatar_url}
                  <img
                    src={member.avatar_url}
                    alt={`Аватар @${member.username}`}
                    class="h-full w-full object-cover"
                    loading="lazy"
                  />
                {:else}
                  {userInitials(member.username)}
                {/if}
              </a>
            {/each}
          </div>
        </div>
      {/if}

      <div class="flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          class="rounded-full px-3 py-1.5 text-sm border transition-colors {selectedCategorySlug ? 'border-slate-200 dark:border-zinc-800 hover:bg-slate-50 dark:hover:bg-zinc-800/60' : 'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300'}"
          on:click={() => setCategoryFilter('')}
          disabled={loadingCategory}
        >
          Все
        </button>
        {#each comun?.categories ?? [] as category}
          <button
            type="button"
            class="rounded-full px-3 py-1.5 text-sm border transition-colors {selectedCategorySlug === category.slug ? 'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300' : 'border-slate-200 dark:border-zinc-800 hover:bg-slate-50 dark:hover:bg-zinc-800/60'}"
            on:click={() => setCategoryFilter(category.slug)}
            disabled={loadingCategory}
            title={category.description || category.name}
          >
            {category.name}
          </button>
        {/each}
      </div>
    </div>
  </section>

  {#if roadmapModalVisible}
    <Portal class="public-roadmap-portal-root">
      <div
        class="public-roadmap-modal fixed inset-0 z-[1200] flex h-screen w-screen items-stretch justify-stretch p-0"
        style="position: fixed; inset: 0; width: 100vw; height: 100dvh; z-index: 2147483000; margin: 0;"
        role="dialog"
        aria-modal="true"
        aria-label="Публичная дорожная карта"
      >
        <button
          type="button"
          class="public-roadmap-modal__backdrop absolute inset-0"
          on:click={closePublicRoadmapModal}
          aria-label="Закрыть дорожную карту"
        ></button>
        <section
          class="public-roadmap-modal__panel relative z-10 flex h-screen w-screen flex-col overflow-hidden"
          style="position: relative; width: 100vw; height: 100dvh;"
        >
          <header class="public-roadmap-modal__header flex items-center justify-between gap-3 px-3 py-2 sm:px-4">
            <div class="min-w-0">
              <div class="truncate text-sm font-semibold text-slate-900 dark:text-zinc-100">
                Публичная дорожная карта
              </div>
              <div class="truncate text-xs text-slate-500 dark:text-zinc-400">
                {comun?.name ?? 'Комуна'}
              </div>
            </div>
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="inline-flex items-center rounded-lg border border-slate-200 dark:border-zinc-700 px-3 py-1.5 text-xs sm:text-sm hover:bg-slate-50 dark:hover:bg-zinc-800/60"
                on:click={closePublicRoadmapModal}
                aria-label="Закрыть дорожную карту"
                title="Закрыть (Esc)"
              >
                Закрыть
              </button>
            </div>
          </header>
          <div class="public-roadmap-modal__content min-h-0 flex-1 overflow-y-auto">
            <div class="mx-auto w-full max-w-[1600px] p-3 sm:p-4 md:p-5">
              <section class="roadmap-shell rounded-3xl overflow-hidden">
      <div class="roadmap-glow"></div>
      <div class="roadmap-content p-4 sm:p-5 md:p-6 flex flex-col gap-5">
        <div class="roadmap-hero grid gap-4">
          <div class="roadmap-hero-card rounded-2xl p-4 sm:p-5 flex flex-col gap-3">
            <div class="space-y-2">
              <h2 class="roadmap-title">
                Показывайте, что будет дальше, и собирайте обратную связь в одном месте
              </h2>
            </div>
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div class="roadmap-stat-card rounded-xl p-3">
                <div class="roadmap-stat-label">В дорожной карте всего</div>
                <div class="roadmap-stat-value">{formatRoadmapCount(roadmapTrackedCount)}</div>
              </div>
              <div class="roadmap-stat-card rounded-xl p-3">
                <div class="roadmap-stat-label">Готово</div>
                <div class="roadmap-stat-value">{formatRoadmapCount(roadmapReleasedCount)}</div>
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              {#if roadmapSelectedStage}
                <Button color="ghost" on:click={() => void setCategoryFilter('')}>Показать все посты</Button>
              {/if}
            </div>
          </div>
        </div>

        <div class="grid gap-3 lg:grid-cols-3">
          {#each roadmapStages as stage}
            {@const preview = getRoadmapPreviewState(stage.key)}
            <section
              class="roadmap-lane rounded-2xl p-4 flex flex-col gap-3"
              data-stage={stage.key}
              style={roadmapStageStyleVars(stage.key)}
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="roadmap-lane-kicker">{stage.shortLabel}</div>
                  <div class="text-sm font-semibold text-slate-900 dark:text-zinc-100 truncate">
                    {stage.category.name}
                  </div>
                  <div class="text-xs text-slate-500 dark:text-zinc-400">
                    {formatRoadmapCount(stage.count)} карточек
                  </div>
                </div>
              </div>

              {#if preview.error}
                <div class="roadmap-lane-state roadmap-lane-state--error">{preview.error}</div>
              {:else if preview.posts.length}
                <div class="flex flex-col gap-2">
                  {#each preview.posts as item}
                    {@const itemSnippet = roadmapSnippet(item)}
                    {@const itemDate = formatRoadmapDate(item.created_at)}
                    <a
                      href={buildBackendPostPath(item)}
                      class="roadmap-mini-card rounded-xl p-3 flex flex-col gap-2"
                      title="Открыть карточку и обсуждение"
                    >
                      <div class="roadmap-mini-title">{item.title || 'Без заголовка'}</div>
                      {#if itemSnippet}
                        <div class="roadmap-mini-snippet">{itemSnippet}</div>
                      {/if}
                      <div class="roadmap-mini-meta">
                        <span>Голоса: {formatRoadmapCount(item.likes_count ?? 0)}</span>
                        <span>Комментарии: {formatRoadmapCount(item.comments_count ?? 0)}</span>
                        {#if itemDate}
                          <span>{itemDate}</span>
                        {/if}
                      </div>
                    </a>
                  {/each}
                </div>
              {:else if !preview.loading}
                <div class="roadmap-lane-state">{stage.emptyState}</div>
              {/if}
            </section>
          {/each}
        </div>

        <div class="roadmap-footer rounded-2xl p-4 flex items-center justify-start">
          <Button on:click={openRoadmapSubmitFlow}>
            Добавить предложение
          </Button>
        </div>
      </div>
              </section>
            </div>
          </div>
        </section>
      </div>
    </Portal>
  {/if}

  {#if isModerator() && comun?.slug}
    <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 sm:p-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="text-sm text-slate-600 dark:text-zinc-400">
          Опубликуйте запись прямо в коммуну. Тег продукта будет подставлен автоматически.
        </div>
        <Button on:click={() => goto(`/comuns/${comun.slug}/new-post`)}>
          Добавить
        </Button>
      </div>
    </section>
  {/if}

  {#if comun?.welcome_post}
    <section class="rounded-2xl border border-blue-200 dark:border-blue-900/60 bg-blue-50/60 dark:bg-blue-950/20 p-4 sm:p-5">
      <div class="mb-3 text-sm font-semibold text-blue-800 dark:text-blue-300">
        Приветственный пост
      </div>
      <Post
        post={welcomePostView}
        class="rounded-2xl border border-slate-200/80 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 shadow-sm px-4 sm:px-5"
        view="cozy"
        actions={true}
        showReadMore={false}
        showFullBody={false}
        linkOverride={buildBackendPostPath(comun.welcome_post)}
        userUrlOverride={comun.welcome_post.author?.username ? `/${comun.welcome_post.author.username}` : undefined}
        communityUrlOverride={comun.welcome_post.rubric_slug ? `/rubrics/${comun.welcome_post.rubric_slug}/posts` : undefined}
        subscribeUrl={comun.welcome_post.channel_url ?? comun.welcome_post.author?.channel_url}
        subscribeLabel="Подписаться"
      />
    </section>
  {/if}

  {#if visiblePosts.length}
    <div class="flex flex-col gap-6" use:feedKeyboardShortcuts>
      {#each visiblePosts as backendPost (backendPost.id)}
        <div class="flex flex-col gap-3">
          <Post
            post={backendPostToPostView(backendPost)}
            class="feed-shortcut-post rounded-2xl border border-slate-200/80 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 shadow-sm px-4 sm:px-5"
            view="cozy"
            actions={true}
            showReadMore={false}
            showFullBody={false}
            linkOverride={buildBackendPostPath(backendPost)}
            userUrlOverride={backendPost.author?.username ? `/${backendPost.author.username}` : undefined}
            communityUrlOverride={backendPost.rubric_slug ? `/rubrics/${backendPost.rubric_slug}/posts` : undefined}
            subscribeUrl={backendPost.channel_url ?? backendPost.author?.channel_url}
            subscribeLabel="Подписаться"
          />

          {#if isModerator()}
            <div class="rounded-xl border border-slate-200 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/60 p-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div class="flex flex-col gap-1 min-w-0">
                <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">Категория внутри комуны</div>
                <div class="flex flex-wrap items-center gap-2">
                  <select
                    class="rounded-lg border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2 py-1 text-sm"
                    value={backendPost.comun_category_id ?? ''}
                    on:change={(event) => onPostCategoryChange(event, backendPost.id)}
                    disabled={categorySavingPostIds.has(backendPost.id)}
                  >
                    <option value="">Без категории</option>
                    {#each comun?.categories ?? [] as category}
                      <option value={category.id}>{category.name}</option>
                    {/each}
                  </select>
                  {#if backendPost.comun_category}
                    <span class="text-xs rounded-full bg-slate-100 dark:bg-zinc-800 px-2 py-1">
                      {backendPost.comun_category.name}
                    </span>
                  {/if}
                </div>
              </div>
              <div class="flex flex-wrap gap-2">
                {#if canMovePostToBacklog(backendPost)}
                  <Button
                    color="ghost"
                    size="sm"
                    on:click={() => movePostToBacklog(backendPost.id)}
                    disabled={categorySavingPostIds.has(backendPost.id)}
                    title="Перевести пост из Предложений в Беклог"
                  >
                    В Беклог
                  </Button>
                {/if}
                <Button
                  color="ghost"
                  size="sm"
                  on:click={() => setWelcomePost(backendPost.id)}
                >
                  Сделать приветственным
                </Button>
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </div>
    {#if loadingMore}
      <div class="text-sm text-slate-500">Загрузка...</div>
    {/if}
  {:else}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-slate-600 dark:text-zinc-400">
      {#if comun?.product_tag}
        В этой комуне пока нет публикаций по тегу #{comun.product_tag.name}.
      {:else}
        Модератору нужно выбрать тег продукта в настройках комуны, чтобы сюда начали попадать посты.
      {/if}
    </div>
  {/if}
</div>

<Modal bind:open={settingsOpen} dismissable={settingsCanDismiss} dismissOnBackdrop={true}>
  <div class="w-full max-w-3xl flex flex-col gap-4">
    <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Настройки комуны</div>
    {#if settingsError}
      <div class="rounded-xl border border-rose-200 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-950/20 px-3 py-2 text-sm text-rose-700 dark:text-rose-300">
        {settingsError}
      </div>
    {/if}

    {#if settingsLoading}
      <div class="text-sm text-slate-500">Загрузка настроек...</div>
    {:else if settingsDraft}
      <div class="grid gap-4">
        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Веб-сайт</span>
          <input bind:value={settingsDraft.website_url} type="url" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2" />
        </label>

        <div class="flex flex-col gap-2">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Логотип</span>
          <input
            bind:this={settingsLogoInput}
            type="file"
            accept="image/*"
            class="hidden"
            on:change={onSettingsLogoSelected}
          />
          <div class="flex items-center gap-3 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-3">
            <div class="h-14 w-14 rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
              {#if settingsDraft.logo_url}
                <img src={settingsDraft.logo_url} alt="Предпросмотр логотипа" class="h-full w-full object-cover" />
              {:else}
                <div class="h-full w-full grid place-items-center text-slate-400 dark:text-zinc-500 text-xs text-center px-1">
                  Нет лого
                </div>
              {/if}
            </div>
            <div class="min-w-0 flex-1 flex flex-col gap-1">
              <div class="text-sm text-slate-700 dark:text-zinc-300">
                {#if settingsLogoUploading}
                  Загрузка логотипа...
                {:else if settingsDraft.logo_url}
                  Логотип выбран
                {:else}
                  Загрузите файл изображения
                {/if}
              </div>
              <div class="text-xs text-slate-500 dark:text-zinc-400">
                PNG, JPG, WEBP, GIF
              </div>
            </div>
            <div class="flex flex-wrap gap-2 justify-end">
              <Button size="sm" on:click={pickSettingsLogo} disabled={settingsSaving || settingsLogoUploading}>
                {settingsDraft.logo_url ? 'Заменить' : 'Выбрать файл'}
              </Button>
              {#if settingsDraft.logo_url}
                <Button
                  color="ghost"
                  size="sm"
                  on:click={() => (settingsDraft = { ...settingsDraft, logo_url: '' })}
                  disabled={settingsSaving || settingsLogoUploading}
                >
                  Убрать
                </Button>
              {/if}
            </div>
          </div>
        </div>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Описание продукта</span>
          <textarea bind:value={settingsDraft.product_description} rows="4" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"></textarea>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Целевая аудитория</span>
          <textarea bind:value={settingsDraft.target_audience} rows="2" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"></textarea>
        </label>

        {#if canManageComunModerators()}
          <div class="flex flex-col gap-2 rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-3">
            <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">Видимость постов комуны в общих лентах</div>
            <label class="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={!settingsDraft.hide_from_home}
                on:change={() =>
                  (settingsDraft = {
                    ...settingsDraft,
                    hide_from_home: !Boolean(settingsDraft.hide_from_home),
                  })}
                class="mt-0.5"
              />
              <span class="min-w-0">
                <span class="block text-sm text-slate-900 dark:text-zinc-100">Показывать в Горячем</span>
                <span class="block text-xs text-slate-500 dark:text-zinc-400">
                  Если выключить, посты, созданные в этой комуне, не попадут на главную.
                </span>
              </span>
            </label>
            <label class="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={!settingsDraft.hide_from_fresh}
                on:change={() =>
                  (settingsDraft = {
                    ...settingsDraft,
                    hide_from_fresh: !Boolean(settingsDraft.hide_from_fresh),
                  })}
                class="mt-0.5"
              />
              <span class="min-w-0">
                <span class="block text-sm text-slate-900 dark:text-zinc-100">Показывать в Свежее</span>
                <span class="block text-xs text-slate-500 dark:text-zinc-400">
                  Если выключить, посты, созданные в этой комуне, останутся только в ленте комуны и персональных лентах.
                </span>
              </span>
            </label>
          </div>
        {/if}

        {#if canManageComunModerators()}
          <div class="flex flex-col gap-2">
            <div class="text-sm text-slate-700 dark:text-zinc-300">Модераторы комуны</div>
            <div class="text-xs text-slate-500 dark:text-zinc-400">
              Только создатель комуны может назначать и снимать модераторов. Создатель всегда остается модератором.
            </div>
            <input
              bind:value={settingsUserSearch}
              placeholder="Поиск пользователя по имени или логину..."
              class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            />
            <div class="max-h-52 overflow-auto rounded-xl border border-slate-200 dark:border-zinc-800 divide-y divide-slate-100 dark:divide-zinc-800">
              {#if filteredUserOptions.length}
                {#each filteredUserOptions as user}
                  <div class="flex items-center justify-between gap-2 px-3 py-2">
                    <div class="min-w-0">
                      <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">
                        {userDisplayName(user)}
                      </div>
                      <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">@{user.username}</div>
                    </div>
                    <Button
                      size="sm"
                      on:click={() => addDraftModerator(user.id)}
                      disabled={draftModeratorIdSet.has(user.id)}
                    >
                      {draftModeratorIdSet.has(user.id) ? 'Добавлен' : 'Добавить'}
                    </Button>
                  </div>
                {/each}
              {:else}
                <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">Пользователи не найдены</div>
              {/if}
            </div>
            <div class="flex flex-col gap-2">
              <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">Выбранные модераторы</div>
              <div class="flex flex-col gap-2">
                {#each selectedModeratorUsers as user}
                  <div class="flex items-center justify-between gap-2 rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2">
                    <div class="min-w-0">
                      <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">
                        {userDisplayName(user)}
                      </div>
                      <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">@{user.username}</div>
                    </div>
                    <Button
                      color="ghost"
                      size="sm"
                      on:click={() => removeDraftModerator(user.id)}
                      disabled={user.id === comun?.creator?.id}
                      title={user.id === comun?.creator?.id ? 'Создателя нельзя убрать из модераторов' : 'Убрать модератора'}
                    >
                      Убрать
                    </Button>
                  </div>
                {/each}
              </div>
            </div>
          </div>
        {/if}

        <div class="flex flex-col gap-2">
          <div class="text-sm text-slate-700 dark:text-zinc-300">Тег продукта (посты с этим тегом попадут в коммуну)</div>
          <div class="flex flex-wrap items-center gap-2">
            {#if settingsDraft.product_tag}
              <span class="rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1 text-sm">
                #{settingsDraft.product_tag.name}
              </span>
              <Button color="ghost" size="sm" on:click={clearDraftTag}>Сбросить</Button>
            {:else}
              <span class="text-sm text-slate-500 dark:text-zinc-400">Тег не выбран</span>
            {/if}
          </div>
          <input
            bind:value={settingsTagSearch}
            placeholder="Поиск тега..."
            class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
          />
          <div class="max-h-48 overflow-auto rounded-xl border border-slate-200 dark:border-zinc-800 divide-y divide-slate-100 dark:divide-zinc-800">
            {#if normalizedTagCreateValue && !hasExactTagMatch}
              <div class="flex items-center justify-between gap-2 px-3 py-2 bg-slate-50 dark:bg-zinc-900/60">
                <div class="min-w-0 text-sm">
                  <div class="font-medium text-slate-900 dark:text-zinc-100 truncate">
                    Добавить тег #{normalizedTagCreateValue}
                  </div>
                  <div class="text-xs text-slate-500 dark:text-zinc-400">
                    Создаст тег в системе и выберет его для комуны
                  </div>
                </div>
                <Button
                  size="sm"
                  on:click={createTagAndChooseDraft}
                  disabled={settingsTagCreating || settingsSaving}
                >
                  {settingsTagCreating ? '...' : 'Добавить'}
                </Button>
              </div>
            {/if}
            {#if filteredTagOptions.length}
              {#each filteredTagOptions as tag}
                <div class="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                  <div class="min-w-0">
                    <div class="font-medium text-slate-900 dark:text-zinc-100 truncate">{tag.name}</div>
                    {#if tag.lemma}
                      <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">{tag.lemma}</div>
                    {/if}
                  </div>
                  <Button size="sm" on:click={() => chooseDraftTag(tag)} disabled={settingsTagCreating || settingsSaving}>Выбрать</Button>
                </div>
              {/each}
            {:else}
              <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">
                {normalizedTagCreateValue && !hasExactTagMatch ? 'Можно добавить новый тег выше' : 'Ничего не найдено'}
              </div>
            {/if}
          </div>
        </div>

        <div class="flex flex-col gap-2">
          <div class="text-sm text-slate-700 dark:text-zinc-300">Внутренние категории</div>
          <div class="grid gap-2 sm:grid-cols-2">
            {#each settingsCategoryOptions as category}
              <label class="rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2 flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={draftCategoryIdSet.has(category.id)}
                  on:change={() => toggleDraftCategory(category.id)}
                  class="mt-0.5"
                />
                <span class="min-w-0">
                  <span class="block text-sm font-medium text-slate-900 dark:text-zinc-100">{category.name}</span>
                  {#if category.description}
                    <span class="block text-xs text-slate-500 dark:text-zinc-400">{category.description}</span>
                  {/if}
                </span>
              </label>
            {/each}
          </div>
        </div>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Приветственный пост (ID или ссылка на пост)</span>
          <input
            bind:value={settingsDraft.welcome_post_ref}
            placeholder="/b/post/123... или 123"
            class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
          />
        </label>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <Button on:click={saveSettings} disabled={settingsSaving || settingsLogoUploading}>
          {settingsSaving ? 'Сохраняем...' : 'Сохранить'}
        </Button>
      </div>
    {/if}
  </div>
</Modal>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
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
  .comun-logo-fallback {
    background: hsl(var(--comun-h, 220) 60% 92%);
    color: hsl(var(--comun-h, 220) 70% 34%);
  }

  :global(.dark) .comun-logo-fallback {
    background: hsl(var(--comun-h, 220) 35% 20%);
    color: hsl(var(--comun-h, 220) 78% 72%);
  }

  .roadmap-shell {
    position: relative;
    border: 1px solid rgba(148, 163, 184, 0.28);
    background:
      radial-gradient(
        circle at 16% 12%,
        rgba(59, 130, 246, 0.1),
        rgba(59, 130, 246, 0) 42%
      ),
      radial-gradient(
        circle at 90% 10%,
        rgba(168, 85, 247, 0.12),
        rgba(168, 85, 247, 0) 38%
      ),
      linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.94));
    box-shadow: 0 20px 60px rgba(15, 23, 42, 0.08);
  }

  :global(.dark) .roadmap-shell {
    border-color: rgba(63, 63, 70, 0.9);
    background:
      radial-gradient(
        circle at 16% 12%,
        rgba(59, 130, 246, 0.16),
        rgba(59, 130, 246, 0) 42%
      ),
      radial-gradient(
        circle at 90% 10%,
        rgba(168, 85, 247, 0.18),
        rgba(168, 85, 247, 0) 38%
      ),
      linear-gradient(180deg, rgba(24, 24, 27, 0.94), rgba(10, 10, 11, 0.96));
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
  }

  .roadmap-glow {
    position: absolute;
    inset: -2px;
    pointer-events: none;
    border-radius: 1.6rem;
    background:
      linear-gradient(115deg, rgba(59, 130, 246, 0.22), rgba(234, 88, 12, 0.14), rgba(16, 185, 129, 0.16));
    filter: blur(24px);
    opacity: 0.45;
  }

  :global(.dark) .roadmap-glow {
    opacity: 0.35;
  }

  .roadmap-content {
    position: relative;
    z-index: 1;
  }

  .roadmap-hero-card,
  .roadmap-insights,
  .roadmap-footer {
    border: 1px solid rgba(148, 163, 184, 0.22);
    background: rgba(255, 255, 255, 0.78);
    backdrop-filter: blur(8px);
  }

  :global(.dark) .roadmap-hero-card,
  :global(.dark) .roadmap-insights,
  :global(.dark) .roadmap-footer {
    border-color: rgba(63, 63, 70, 0.85);
    background: rgba(24, 24, 27, 0.72);
  }

  .roadmap-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border-radius: 9999px;
    padding: 0.35rem 0.65rem;
    border: 1px solid rgba(59, 130, 246, 0.25);
    background: rgba(239, 246, 255, 0.8);
    color: rgb(30 64 175);
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  .roadmap-badge--muted {
    border-color: hsla(var(--roadmap-stage-h), var(--roadmap-stage-s), 34%, 0.22);
    background: hsla(var(--roadmap-stage-h), 85%, 96%, 0.9);
    color: hsl(var(--roadmap-stage-h) 58% 30%);
  }

  :global(.dark) .roadmap-badge {
    border-color: rgba(59, 130, 246, 0.35);
    background: rgba(30, 41, 59, 0.72);
    color: rgb(147 197 253);
  }

  :global(.dark) .roadmap-badge--muted {
    border-color: hsla(var(--roadmap-stage-h), 45%, 55%, 0.32);
    background: hsla(var(--roadmap-stage-h), 42%, 16%, 0.55);
    color: hsl(var(--roadmap-stage-h) 86% 80%);
  }

  .roadmap-title {
    font-size: clamp(1.15rem, 1.1rem + 0.8vw, 1.55rem);
    line-height: 1.2;
    font-weight: 700;
    color: rgb(15 23 42);
  }

  .roadmap-subtitle {
    color: rgb(71 85 105);
    line-height: 1.5;
    font-size: 0.95rem;
  }

  :global(.dark) .roadmap-title {
    color: rgb(244 244 245);
  }

  :global(.dark) .roadmap-subtitle {
    color: rgb(161 161 170);
  }

  .roadmap-help {
    border: 1px dashed rgba(148, 163, 184, 0.35);
    background: rgba(248, 250, 252, 0.75);
    color: rgb(51 65 85);
  }

  :global(.dark) .roadmap-help {
    border-color: rgba(82, 82, 91, 0.9);
    background: rgba(9, 9, 11, 0.36);
    color: rgb(212 212 216);
  }

  .roadmap-stat-card {
    border: 1px solid rgba(148, 163, 184, 0.2);
    background: rgba(248, 250, 252, 0.82);
  }

  :global(.dark) .roadmap-stat-card {
    border-color: rgba(63, 63, 70, 0.85);
    background: rgba(9, 9, 11, 0.38);
  }

  .roadmap-stat-label {
    font-size: 0.7rem;
    line-height: 1.1;
    color: rgb(100 116 139);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .roadmap-stat-value {
    margin-top: 0.35rem;
    font-weight: 700;
    font-size: 1.05rem;
    line-height: 1.2;
    color: rgb(15 23 42);
  }

  .roadmap-stat-note {
    margin-top: 0.2rem;
    font-size: 0.75rem;
    color: rgb(100 116 139);
  }

  :global(.dark) .roadmap-stat-label,
  :global(.dark) .roadmap-stat-note {
    color: rgb(161 161 170);
  }

  :global(.dark) .roadmap-stat-value {
    color: rgb(244 244 245);
  }

  .roadmap-steps {
    margin-top: 0.1rem;
  }

  .roadmap-step {
    display: grid;
    grid-template-columns: 1.4rem 1fr;
    gap: 0.6rem;
    align-items: start;
    font-size: 0.82rem;
    line-height: 1.35;
    color: rgb(71 85 105);
    padding: 0.35rem 0;
  }

  .roadmap-step > span {
    display: grid;
    place-items: center;
    width: 1.4rem;
    height: 1.4rem;
    border-radius: 9999px;
    font-weight: 700;
    color: rgb(30 64 175);
    background: rgba(219, 234, 254, 0.95);
    border: 1px solid rgba(96, 165, 250, 0.25);
  }

  :global(.dark) .roadmap-step {
    color: rgb(212 212 216);
  }

  :global(.dark) .roadmap-step > span {
    color: rgb(191 219 254);
    background: rgba(30, 41, 59, 0.8);
    border-color: rgba(59, 130, 246, 0.35);
  }

  .roadmap-stage-tile {
    position: relative;
    border: 1px solid rgba(148, 163, 184, 0.22);
    background:
      linear-gradient(
        180deg,
        hsla(var(--roadmap-stage-h), 95%, 96%, 0.9),
        rgba(255, 255, 255, 0.88)
      );
    transition:
      transform 0.16s ease,
      box-shadow 0.16s ease,
      border-color 0.16s ease;
  }

  .roadmap-stage-tile:hover {
    transform: translateY(-1px);
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.07);
    border-color: hsla(var(--roadmap-stage-h), 78%, 45%, 0.28);
  }

  .roadmap-stage-tile.is-selected {
    border-color: hsla(var(--roadmap-stage-h), 78%, 45%, 0.45);
    box-shadow:
      0 0 0 1px hsla(var(--roadmap-stage-h), 78%, 45%, 0.24) inset,
      0 10px 28px rgba(15, 23, 42, 0.08);
  }

  :global(.dark) .roadmap-stage-tile {
    border-color: rgba(63, 63, 70, 0.85);
    background:
      linear-gradient(
        180deg,
        hsla(var(--roadmap-stage-h), 46%, 13%, 0.48),
        rgba(24, 24, 27, 0.86)
      );
  }

  :global(.dark) .roadmap-stage-tile:hover {
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.28);
    border-color: hsla(var(--roadmap-stage-h), 72%, 55%, 0.34);
  }

  :global(.dark) .roadmap-stage-tile.is-selected {
    border-color: hsla(var(--roadmap-stage-h), 76%, 60%, 0.46);
    box-shadow:
      0 0 0 1px hsla(var(--roadmap-stage-h), 72%, 58%, 0.26) inset,
      0 10px 24px rgba(0, 0, 0, 0.32);
  }

  .roadmap-stage-pill {
    display: inline-flex;
    align-items: center;
    border-radius: 9999px;
    padding: 0.2rem 0.55rem;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: hsl(var(--roadmap-stage-h) 60% 30%);
    background: hsla(var(--roadmap-stage-h), 90%, 92%, 0.95);
    border: 1px solid hsla(var(--roadmap-stage-h), 88%, 56%, 0.22);
  }

  .roadmap-stage-count {
    font-weight: 700;
    font-size: 0.95rem;
    color: rgb(15 23 42);
  }

  :global(.dark) .roadmap-stage-pill {
    color: hsl(var(--roadmap-stage-h) 88% 82%);
    background: hsla(var(--roadmap-stage-h), 46%, 18%, 0.72);
    border-color: hsla(var(--roadmap-stage-h), 62%, 52%, 0.24);
  }

  :global(.dark) .roadmap-stage-count {
    color: rgb(244 244 245);
  }

  .roadmap-lane {
    border: 1px solid rgba(148, 163, 184, 0.2);
    background:
      linear-gradient(
        180deg,
        hsla(var(--roadmap-stage-h), 92%, 97%, 0.75),
        rgba(255, 255, 255, 0.84)
      );
  }

  :global(.dark) .roadmap-lane {
    border-color: rgba(63, 63, 70, 0.85);
    background:
      linear-gradient(
        180deg,
        hsla(var(--roadmap-stage-h), 40%, 13%, 0.38),
        rgba(24, 24, 27, 0.84)
      );
  }

  .roadmap-lane-kicker {
    display: inline-flex;
    align-items: center;
    border-radius: 9999px;
    padding: 0.2rem 0.55rem;
    font-size: 0.68rem;
    line-height: 1;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: hsl(var(--roadmap-stage-h) 60% 30%);
    background: hsla(var(--roadmap-stage-h), 95%, 93%, 0.92);
    border: 1px solid hsla(var(--roadmap-stage-h), 88%, 56%, 0.2);
    margin-bottom: 0.4rem;
  }

  :global(.dark) .roadmap-lane-kicker {
    color: hsl(var(--roadmap-stage-h) 90% 82%);
    background: hsla(var(--roadmap-stage-h), 48%, 18%, 0.6);
    border-color: hsla(var(--roadmap-stage-h), 64%, 52%, 0.22);
  }

  .roadmap-mini-card {
    border: 1px solid rgba(148, 163, 184, 0.18);
    background: rgba(255, 255, 255, 0.85);
    transition:
      transform 0.14s ease,
      box-shadow 0.14s ease,
      border-color 0.14s ease;
  }

  .roadmap-mini-card:hover {
    transform: translateY(-1px);
    border-color: hsla(var(--roadmap-stage-h), 80%, 48%, 0.28);
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.07);
  }

  :global(.dark) .roadmap-mini-card {
    border-color: rgba(63, 63, 70, 0.78);
    background: rgba(9, 9, 11, 0.34);
  }

  :global(.dark) .roadmap-mini-card:hover {
    border-color: hsla(var(--roadmap-stage-h), 70%, 56%, 0.3);
    box-shadow: 0 8px 18px rgba(0, 0, 0, 0.22);
  }

  .roadmap-mini-title {
    font-size: 0.88rem;
    font-weight: 600;
    line-height: 1.25;
    color: rgb(15 23 42);
    line-clamp: 2;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .roadmap-mini-snippet {
    font-size: 0.78rem;
    line-height: 1.4;
    color: rgb(71 85 105);
    line-clamp: 3;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .roadmap-mini-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem 0.65rem;
    font-size: 0.72rem;
    color: rgb(100 116 139);
  }

  :global(.dark) .roadmap-mini-title {
    color: rgb(244 244 245);
  }

  :global(.dark) .roadmap-mini-snippet {
    color: rgb(161 161 170);
  }

  :global(.dark) .roadmap-mini-meta {
    color: rgb(161 161 170);
  }

  .roadmap-lane-state {
    border-radius: 0.9rem;
    border: 1px dashed rgba(148, 163, 184, 0.28);
    background: rgba(248, 250, 252, 0.72);
    color: rgb(71 85 105);
    font-size: 0.82rem;
    line-height: 1.4;
    padding: 0.85rem;
  }

  .roadmap-lane-state--error {
    border-color: rgba(244, 63, 94, 0.28);
    background: rgba(255, 241, 242, 0.78);
    color: rgb(159 18 57);
  }

  :global(.dark) .roadmap-lane-state {
    border-color: rgba(82, 82, 91, 0.9);
    background: rgba(9, 9, 11, 0.32);
    color: rgb(212 212 216);
  }

  :global(.dark) .roadmap-lane-state--error {
    border-color: rgba(190, 24, 93, 0.3);
    background: rgba(80, 7, 36, 0.3);
    color: rgb(253 164 175);
  }

  .public-roadmap-modal {
    overscroll-behavior: contain;
  }

  :global(.portal-content.public-roadmap-portal-root) {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    height: 100dvh !important;
    margin: 0 !important;
    padding: 0 !important;
    z-index: 2147483000 !important;
    transform: none !important;
    contain: none !important;
    pointer-events: none;
  }

  :global(.portal-content.public-roadmap-portal-root > .public-roadmap-modal) {
    pointer-events: auto;
  }

  .public-roadmap-modal__backdrop {
    padding: 0;
    margin: 0;
    border: 0;
    width: 100%;
    height: 100%;
    cursor: default;
    background:
      radial-gradient(circle at 14% 10%, rgba(59, 130, 246, 0.18), transparent 52%),
      radial-gradient(circle at 86% 12%, rgba(236, 72, 153, 0.14), transparent 48%),
      rgba(2, 6, 23, 0.52);
    backdrop-filter: blur(10px);
  }

  .public-roadmap-modal__panel {
    background: rgba(255, 255, 255, 0.96);
    border: 1px solid rgba(148, 163, 184, 0.24);
    box-shadow: 0 22px 70px rgba(15, 23, 42, 0.24);
  }

  :global(.dark) .public-roadmap-modal__panel {
    background: rgba(9, 9, 11, 0.96);
    border-color: rgba(63, 63, 70, 0.65);
    box-shadow: 0 22px 70px rgba(0, 0, 0, 0.45);
  }

  .public-roadmap-modal__header {
    border-bottom: 1px solid rgba(148, 163, 184, 0.18);
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.7)),
      radial-gradient(circle at 8% 18%, rgba(59, 130, 246, 0.09), transparent 60%);
    backdrop-filter: blur(6px);
  }

  :global(.dark) .public-roadmap-modal__header {
    border-bottom-color: rgba(82, 82, 91, 0.72);
    background:
      linear-gradient(180deg, rgba(9, 9, 11, 0.92), rgba(9, 9, 11, 0.78)),
      radial-gradient(circle at 8% 18%, rgba(59, 130, 246, 0.12), transparent 60%);
  }

  .public-roadmap-modal__content {
    background: rgba(248, 250, 252, 0.95);
  }

  :global(.dark) .public-roadmap-modal__content {
    background: rgba(9, 9, 11, 0.95);
  }

  @media (max-width: 640px) {
    .public-roadmap-modal__header {
      padding-top: calc(env(safe-area-inset-top) + 0.55rem);
    }
  }
</style>
